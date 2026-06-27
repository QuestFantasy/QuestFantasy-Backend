from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MarketplaceListing, PlayerItem, PlayerProfile, PlayerSkill, PlayerPendingDrop
from .serializers import (
    MarketplaceCreateSerializer,
    MarketplaceListingSerializer,
    PlayerGoldSerializer,
    PlayerGoldUpdateSerializer,
    PlayerInventorySerializer,
    PlayerInventoryUpdateSerializer,
    PlayerProfileSerializer,
    PlayerProfileUpdateSerializer,
    ensure_instance_ids,
    serialize_item,
)


def _validate_new_item(item_data: dict, player_level: int) -> tuple[bool, str]:
    item_type = item_data.get('item_type')
    if not item_type:
        return True, ""

    if item_type in ('potion', 'ticket', 'misc'):
        item_id = item_data.get('item_id')
        if item_type == 'potion':
            if item_id not in ('hp_potion_s', 'hp_potion_m', 'hp_potion_l', 'burn_potion'):
                return False, f"invalid potion item_id: {item_id}"
        elif item_type == 'ticket':
            difficulty = item_data.get('difficulty')
            if difficulty not in ('Easy', 'Normal', 'Hard', 'Nightmare'):
                return False, f"invalid ticket difficulty: {difficulty}"
        return True, ""

    if item_type in ('equipment', 'weapon'):
        try:
            rarity = int(item_data.get('rarity', 1))
        except (ValueError, TypeError):
            return False, "rarity must be an integer"
        if not (1 <= rarity <= 5):
            return False, f"invalid rarity: {rarity}"

        try:
            level_requirement = int(item_data.get('level_requirement', 1))
        except (ValueError, TypeError):
            return False, "level_requirement must be an integer"
        if level_requirement > player_level + 5:
            return False, f"level requirement too high: {level_requirement} for player level {player_level}"

        abilities = item_data.get('abilities', {})
        if not isinstance(abilities, dict):
            return False, "abilities must be a dictionary"

        try:
            atk = int(abilities.get('atk', 0))
            def_val = int(abilities.get('def', 0))
            spd = int(abilities.get('spd', 0))
            vit = int(abilities.get('vit', 0))
        except (ValueError, TypeError):
            return False, "ability values must be integers"

        if atk < 0 or def_val < 0 or spd < 0 or vit < 0:
            return False, "abilities cannot be negative"

        # Theoretical max scaling validation
        level_req = max(1, level_requirement)
        level_factor = 1.0 + max(0, level_req - 1) * 0.03
        rarity_factor = {1: 1.0, 2: 1.2, 3: 1.5, 4: 1.9, 5: 2.4}.get(rarity, 1.0)
        max_stat_limit = (rarity * 8) * level_factor * rarity_factor + 20

        if atk > max_stat_limit or def_val > max_stat_limit or spd > max_stat_limit or vit > max_stat_limit:
            return False, f"stats exceed maximum possible bounds for level {level_req} and rarity {rarity}"

        return True, ""

    return True, ""


def _sync_profile_items(profile: PlayerProfile, *, inventory_items=None, discarded_items=None, pending_drops=None) -> None:
    desired_by_state = {}
    desired_ids = set()

    for state_name, items in (
        (PlayerItem.State.INVENTORY, inventory_items),
        (PlayerItem.State.DISCARDED, discarded_items),
    ):
        if items is None:
            continue

        normalized_items, _ = ensure_instance_ids(items)
        normalized_payloads = []
        state_ids = set()

        for item in normalized_items:
            instance_id = item.get('instance_id')
            if not instance_id:
                raise ValidationError({'detail': 'Each item must include an instance_id.'})

            if instance_id in desired_ids or instance_id in state_ids:
                raise ValidationError({'detail': 'Duplicate instance_id values are not allowed.'})

            state_ids.add(instance_id)
            desired_ids.add(instance_id)
            payload = dict(item)
            payload.pop('instance_id', None)
            normalized_payloads.append((instance_id, payload))

        desired_by_state[state_name] = normalized_payloads

    if not desired_by_state:
        return

    existing_items = {
        str(item.instance_id): item
        for item in profile.items.all()
    }

    for state_name, payloads in desired_by_state.items():
        for instance_id, payload in payloads:
            item = existing_items.pop(instance_id, None)
            if item is None:
                if pending_drops:
                    # Enforce secure drop validation
                    if instance_id not in pending_drops:
                        raise ValidationError({'detail': f'Forged item instance_id: {instance_id}'})
                    
                    pending_drop = pending_drops[instance_id]
                    if not pending_drop.item_data:
                        raise ValidationError({'detail': f'Instance_id {instance_id} is not an item drop.'})
                    
                    authoritative_payload = pending_drop.item_data
                    PlayerItem.objects.create(
                        owner=profile,
                        instance_id=instance_id,
                        item_data=authoritative_payload,
                        state=state_name,
                    )
                    pending_drop.delete()
                else:
                    # Lobby or test case: validate stats and allow creation
                    is_valid, error_msg = _validate_new_item(payload, profile.level)
                    if not is_valid:
                        raise ValidationError({'detail': f'Item validation failed: {error_msg}'})
                    
                    PlayerItem.objects.create(
                        owner=profile,
                        instance_id=instance_id,
                        item_data=payload,
                        state=state_name,
                    )
            else:
                if item.state == PlayerItem.State.LISTED and state_name != PlayerItem.State.LISTED:
                    raise ValidationError({'detail': 'Listed items cannot be modified through inventory sync.'})

                item.owner = profile
                item.item_data = payload
                item.state = state_name
                item.save(update_fields=['owner', 'item_data', 'state', 'updated_at'])

    if inventory_items is not None:
        PlayerItem.objects.filter(
            owner=profile,
            state=PlayerItem.State.INVENTORY,
        ).exclude(instance_id__in=desired_ids).delete()

    if discarded_items is not None:
        PlayerItem.objects.filter(
            owner=profile,
            state=PlayerItem.State.DISCARDED,
        ).exclude(instance_id__in=desired_ids).delete()



class PlayerProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        profile = self._get_or_create_profile(request.user)
        serializer = PlayerProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request: Request) -> Response:
        profile = self._get_or_create_profile(request.user)
        serializer = PlayerProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data

        # -------------------------------------------------------------------
        # Anti-Cheat Validation Checks
        # -------------------------------------------------------------------
        session_id = validated.get('session_id')
        sequence   = validated.get('sequence')
        claimed_drops = validated.get('claimed_drops', [])
        
        # Load pending drops for the profile
        pending_drops = {
            str(drop.instance_id): drop
            for drop in profile.pending_drops.all()
        }

        # 1. Idempotency Check (Sequence numbers)
        if session_id and profile.active_session_id == session_id:
            if sequence is not None and sequence <= profile.last_sequence:
                output = PlayerProfileSerializer(profile).data
                output['ignored'] = True
                output['reason'] = 'stale_sequence'
                return Response(output, status=status.HTTP_200_OK)

        # 2. Gold Check
        if 'gold' in validated:
            new_gold = validated['gold']
            if new_gold > profile.gold:
                # Calculate gold gained from claimed drops
                claimed_gold_from_drops = 0
                for drop_id in claimed_drops:
                    drop = pending_drops.get(drop_id)
                    if drop and drop.gold_amount > 0:
                        claimed_gold_from_drops += drop.gold_amount
                        
                gold_diff = new_gold - profile.gold
                elapsed = (timezone.now() - profile.updated_at).total_seconds()
                max_allowed = 200 + (30 * profile.level) * max(0.0, elapsed)
                if gold_diff > claimed_gold_from_drops + max_allowed:
                    output = PlayerProfileSerializer(profile).data
                    output['ignored'] = True
                    output['reason'] = 'invalid_gold_gain'
                    return Response(output, status=status.HTTP_200_OK)

        # 3. HP Check
        if 'hp_max' in validated and validated['hp_max'] > 10000:
            output = PlayerProfileSerializer(profile).data
            output['ignored'] = True
            output['reason'] = 'invalid_hp_max'
            return Response(output, status=status.HTTP_200_OK)

        # 4. Level & EXP Check
        if 'level' in validated:
            new_level = validated['level']
            if new_level - profile.level > 2:
                output = PlayerProfileSerializer(profile).data
                output['ignored'] = True
                output['reason'] = 'invalid_level_jump'
                return Response(output, status=status.HTTP_200_OK)

        if 'experience' in validated:
            new_exp = validated['experience']
            if new_exp > profile.experience:
                exp_diff = new_exp - profile.experience
                elapsed = (timezone.now() - profile.updated_at).total_seconds()
                max_exp_allowed = 500 + (50 * profile.level) * max(0.0, elapsed)
                if exp_diff > max_exp_allowed:
                    output = PlayerProfileSerializer(profile).data
                    output['ignored'] = True
                    output['reason'] = 'invalid_experience_gain'
                    return Response(output, status=status.HTTP_200_OK)

        # 5. Item Generation (Spawning) Check
        existing_items = {
            str(item.instance_id): item
            for item in profile.items.all()
        }
        for items_key in ('inventory_items', 'discarded_items'):
            items_list = validated.get(items_key)
            if not items_list:
                continue
            for item_dict in items_list:
                instance_id = item_dict.get('instance_id')
                if instance_id and instance_id not in existing_items:
                    is_valid, error_msg = _validate_new_item(item_dict, profile.level)
                    if not is_valid:
                        output = PlayerProfileSerializer(profile).data
                        output['ignored'] = True
                        output['reason'] = f'item_validation_failed: {error_msg}'
                        return Response(output, status=status.HTTP_200_OK)

                    if pending_drops and instance_id not in pending_drops:
                        output = PlayerProfileSerializer(profile).data
                        output['ignored'] = True
                        output['reason'] = f'item_validation_failed: forged_item: {instance_id}'
                        return Response(output, status=status.HTTP_200_OK)

        # -------------------------------------------------------------------
        # End of validation / Apply changes
        # -------------------------------------------------------------------

        with transaction.atomic():
            # Reset sequence counter and clear pending drops when a new session starts.
            if session_id and profile.active_session_id != session_id:
                profile.active_session_id = session_id
                profile.last_sequence = 0
                profile.pending_drops.all().delete()

            # Apply simple scalar fields directly onto the profile.
            for field in ('level', 'experience', 'hp_max', 'hp_current', 'gold', 'class_name', 'equipped_items'):

                if field in validated:
                    setattr(profile, field, validated[field])

            # Sync inventory and discarded items.
            if 'inventory_items' in validated or 'discarded_items' in validated:
                _sync_profile_items(
                    profile,
                    inventory_items=validated.get('inventory_items'),
                    discarded_items=validated.get('discarded_items'),
                    pending_drops=pending_drops,
                )

            # Consume claimed gold drops
            for drop_id in claimed_drops:
                drop = pending_drops.get(drop_id)
                if drop and drop.gold_amount > 0:
                    drop.delete()

            # Replace skills list.
            if 'skills' in validated:
                PlayerSkill.objects.filter(player_profile=profile).delete()
                for index, skill in enumerate(validated['skills']):
                    PlayerSkill.objects.create(
                        player_profile=profile,
                        skill_id=skill['skill_id'],
                        name=skill['name'],
                        cooldown_seconds=skill['cooldown_seconds'],
                        display_order=index,
                    )

            # Guard: hp_current must never exceed hp_max.
            if profile.hp_current > profile.hp_max:
                profile.hp_current = profile.hp_max

            if sequence is not None:
                profile.last_sequence = sequence

            profile.save(update_fields=[
                'level',
                'experience',
                'hp_max',
                'hp_current',
                'gold',
                'class_name',
                'equipped_items',
                'active_session_id',
                'last_sequence',
                'updated_at',
            ])

        output = PlayerProfileSerializer(profile).data
        output['ignored'] = False
        return Response(output, status=status.HTTP_200_OK)


    @staticmethod
    def _get_or_create_profile(user):
        profile, created = PlayerProfile.objects.get_or_create(user=user)
        if created and not PlayerSkill.objects.filter(player_profile=profile).exists():
            defaults = [
                ('basic_attack', 'Sword Attack', 0.3, 0),
                ('bow_attack', 'Bow Attack', 0.6, 1),
                ('fireball', 'Fireball', 1.2, 2),
            ]
            for skill_id, name, cooldown, order in defaults:
                PlayerSkill.objects.create(
                    player_profile=profile,
                    skill_id=skill_id,
                    name=name,
                    cooldown_seconds=cooldown,
                    display_order=order,
                )
        return profile


class PlayerInventoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        profile = PlayerProfileView._get_or_create_profile(request.user)
        serializer = PlayerInventorySerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request: Request) -> Response:
        profile = PlayerProfileView._get_or_create_profile(request.user)
        serializer = PlayerInventoryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data

        with transaction.atomic():
            _sync_profile_items(
                profile,
                inventory_items=validated.get('inventory_items'),
                discarded_items=validated.get('discarded_items'),
            )

            update_fields = ['updated_at']
            if 'equipped_items' in validated:
                profile.equipped_items = validated['equipped_items']
                update_fields.append('equipped_items')

            profile.save(update_fields=update_fields)
        output = PlayerInventorySerializer(profile).data
        return Response(output, status=status.HTTP_200_OK)


class PlayerGoldView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        profile = PlayerProfileView._get_or_create_profile(request.user)
        serializer = PlayerGoldSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request: Request) -> Response:
        profile = PlayerProfileView._get_or_create_profile(request.user)
        serializer = PlayerGoldUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_gold = serializer.validated_data['gold']
        if new_gold > profile.gold:
            gold_diff = new_gold - profile.gold
            elapsed = (timezone.now() - profile.updated_at).total_seconds()
            max_allowed = 200 + (30 * profile.level) * max(0.0, elapsed)
            if gold_diff > max_allowed:
                raise ValidationError({'detail': 'Invalid gold gain detected.'})

        profile.gold = new_gold
        profile.save(update_fields=['gold', 'updated_at'])

        output = PlayerGoldSerializer(profile).data
        return Response(output, status=status.HTTP_200_OK)


class PlayerDropView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        import random
        import uuid
        profile = PlayerProfileView._get_or_create_profile(request.user)
        action = request.data.get('action') # "generate" or "clear"
        
        if action == "clear":
            PlayerPendingDrop.objects.filter(owner=profile).delete()
            return Response({"detail": "Pending drops cleared successfully."}, status=status.HTTP_200_OK)
            
        elif action == "generate":
            player_level = request.data.get('player_level', profile.level)
            drop_source = request.data.get('drop_source', 'chest') # "chest" or "monster" or "lobby"
            difficulty = request.data.get('difficulty', 'Normal')
            
            drops = []
            
            # 1. Gold drop
            base_min = 5 + (player_level - 1) * 2
            base_max = 10 + (player_level - 1) * 4
            base_value = random.randint(base_min, base_max)
            
            diff_mult = {"Easy": 0.75, "Normal": 1.0, "Hard": 2.0, "Nightmare": 4.0}.get(difficulty, 1.0)
            src_mult = {"monster": 0.3, "lobby": 5.0, "chest": 1.0}.get(drop_source, 1.0)
            
            gold_amount = int(base_value * src_mult * diff_mult)
            if gold_amount < 1:
                gold_amount = 1
                
            gold_uuid = str(uuid.uuid4())
            PlayerPendingDrop.objects.create(
                owner=profile,
                instance_id=gold_uuid,
                gold_amount=gold_amount,
                item_data=None
            )
            drops.append({
                "instance_id": gold_uuid,
                "item_type": "gold",
                "gold_amount": gold_amount,
                "item_data": None
            })
            
            # For lobby source, we only drop gold
            if drop_source == "lobby":
                return Response(drops, status=status.HTTP_200_OK)
                
            # 2. Potion drop
            # 18% for chest, 8% for monster. Multiplier = 5.
            potion_chance = 0.18 if drop_source == "chest" else 0.08
            potion_chance = min(1.0, potion_chance * 5.0)
            if random.random() < potion_chance:
                # hp_potion_s, hp_potion_m, hp_potion_l, burn_potion
                pot_roll = random.random()
                if pot_roll < 0.52:
                    p_id, p_name, p_sprite, p_heal, p_burn, p_price = "hp_potion_s", "Small HP Potion", "res://Assets/items/hp_potion_S.png", 5, False, 10
                elif pot_roll < 0.76:
                    p_id, p_name, p_sprite, p_heal, p_burn, p_price = "hp_potion_m", "Medium HP Potion", "res://Assets/items/hp_potion_M.png", 12, False, 24
                elif pot_roll < 0.90:
                    p_id, p_name, p_sprite, p_heal, p_burn, p_price = "burn_potion", "Burn Remedy", "res://Assets/items/burn_potion.png", 0, True, 30
                else:
                    p_id, p_name, p_sprite, p_heal, p_burn, p_price = "hp_potion_l", "Large HP Potion", "res://Assets/items/hp_potion_L.png", 20, False, 40
                
                pot_data = {
                    "item_id": p_id,
                    "name": p_name,
                    "description": f"Restores {p_heal} HP." if p_heal > 0 else "Immediately cures Burn.",
                    "item_type": "potion",
                    "quantity": 1,
                    "price": p_price,
                    "sprite_path": p_sprite,
                    "heal_amount": p_heal,
                    "removes_burn": p_burn
                }
                item_uuid = str(uuid.uuid4())
                PlayerPendingDrop.objects.create(
                    owner=profile,
                    instance_id=item_uuid,
                    gold_amount=0,
                    item_data=pot_data
                )
                drops.append({
                    "instance_id": item_uuid,
                    "item_type": "potion",
                    "gold_amount": 0,
                    "item_data": pot_data
                })
                
            # 3. Ticket drop
            # 2% for chest, 1% for monster. Multiplier = 5.
            ticket_chance = 0.02 if drop_source == "chest" else 0.01
            ticket_chance = min(1.0, ticket_chance * 5.0)
            if random.random() < ticket_chance:
                # normal, hard, nightmare
                ticket_diff = random.choices(
                    ["Normal", "Hard", "Nightmare"],
                    weights=[
                        1.8 if difficulty == "Normal" else 1.0,
                        1.8 if difficulty == "Hard" else 1.0,
                        1.8 if difficulty == "Nightmare" else 1.0
                    ]
                )[0]
                
                t_id = f"ticket_{ticket_diff.lower()}"
                t_name = f"{ticket_diff} Ticket"
                t_sprite = f"res://Assets/items/ticket_{ticket_diff.lower()}.png"
                ticket_data = {
                    "item_id": t_id,
                    "name": t_name,
                    "description": f"Allows one {ticket_diff} dungeon entry.",
                    "item_type": "ticket",
                    "quantity": 1,
                    "price": 0,
                    "sprite_path": t_sprite,
                    "difficulty": ticket_diff
                }
                item_uuid = str(uuid.uuid4())
                PlayerPendingDrop.objects.create(
                    owner=profile,
                    instance_id=item_uuid,
                    gold_amount=0,
                    item_data=ticket_data
                )
                drops.append({
                    "instance_id": item_uuid,
                    "item_type": "ticket",
                    "gold_amount": 0,
                    "item_data": ticket_data
                })

            # 4. Equipment/Weapon drop
            num_eq = 0
            if drop_source == "chest":
                num_eq = random.randint(1, 4)
            elif drop_source == "monster":
                if random.random() < 0.20:
                    num_eq = 1
                    
            for _ in range(num_eq):
                cat = random.choice(["helmet", "chestplate", "gloves", "shoes", "sword", "bow", "staff"])
                is_weapon = cat in ("sword", "bow", "staff")
                
                rar_roll = random.randint(1, 100)
                if rar_roll <= 55: rarity = 1
                elif rar_roll <= 80: rarity = 2
                elif rar_roll <= 92: rarity = 3
                elif rar_roll <= 98: rarity = 4
                else: rarity = 5
                
                req_lv = random.randint(max(1, player_level - 1), player_level + 1)
                
                rar_names = ["Basic", "Fine", "Rare", "Epic", "Legendary"]
                rar_name = rar_names[rarity - 1]
                
                cat_display = {
                    "helmet": "Helmet", "chestplate": "Chestplate", "gloves": "Gloves",
                    "shoes": "Boots", "sword": "Sword", "bow": "Bow", "staff": "Staff"
                }[cat]
                
                disp_name = f"{rar_name} {cat_display}"
                sprite = f"res://Assets/Equipments/{cat}/basic-{cat}.png"
                if cat == "shoes": sprite = "res://Assets/Equipments/shoes/basic-shoes.png"
                elif cat == "gloves": sprite = "res://Assets/Equipments/gloves/basic-gloves.png"
                elif cat == "chestplate": sprite = "res://Assets/Equipments/chestplate/basic-chestplate.png"
                
                base_atk = base_def = base_spd = base_vit = 0
                if cat == "helmet":
                    base_atk, base_def, base_spd, base_vit = rarity, rarity, 0, rarity * 3
                elif cat == "chestplate":
                    base_atk, base_def, base_spd, base_vit = rarity, rarity * 3, 0, rarity * 2
                elif cat == "gloves":
                    base_atk, base_def, base_spd, base_vit = rarity * 2, rarity, rarity, 0
                elif cat == "shoes":
                    base_atk, base_def, base_spd, base_vit = 0, rarity, rarity * 3, rarity
                elif cat == "sword":
                    base_atk, base_def, base_spd, base_vit = rarity * 3, rarity * 2, (1 if rarity >= 3 else 0), 0
                elif cat == "bow":
                    base_atk, base_def, base_spd, base_vit = rarity * 2, rarity, rarity * 3, 0
                elif cat == "staff":
                    base_atk, base_def, base_spd, base_vit = rarity * 5, rarity, (1 if rarity >= 3 else 0), 0
                    
                mults = [1.0, 1.0, 1.2, 1.5, 1.9, 2.4]
                mult = mults[rarity]
                scale = (1.0 + req_lv * 0.03) * mult
                abilities = {
                    "atk": int(base_atk * scale),
                    "def": int(base_def * scale),
                    "spd": int(base_spd * scale),
                    "vit": int(base_vit * scale),
                }
                
                price = rarity * 10 + req_lv * 5
                
                item_data = {
                    "name": disp_name,
                    "description": "",
                    "item_type": "weapon" if is_weapon else "equipment",
                    "quantity": 1,
                    "price": price,
                    "sprite_path": sprite,
                    "rarity": rarity,
                    "level_requirement": req_lv,
                    "source": "Generated",
                    "abilities": abilities
                }
                if is_weapon:
                    item_data["weapon_type"] = cat_display
                else:
                    item_data["equipment_type"] = {"helmet": "Head", "chestplate": "Body", "gloves": "Arms", "shoes": "Shoes"}.get(cat, "Other")
                    
                item_uuid = str(uuid.uuid4())
                PlayerPendingDrop.objects.create(
                    owner=profile,
                    instance_id=item_uuid,
                    gold_amount=0,
                    item_data=item_data
                )
                drops.append({
                    "instance_id": item_uuid,
                    "item_type": "weapon" if is_weapon else "equipment",
                    "gold_amount": 0,
                    "item_data": item_data
                })

            return Response(drops, status=status.HTTP_200_OK)
            
        return Response({"detail": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Marketplace views
# ---------------------------------------------------------------------------

class MarketplaceListView(APIView):
    """
    GET  /api/player/marketplace/   — List all active listings.
    POST /api/player/marketplace/   — Create a new listing (removes item from inventory).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        listings = (
            MarketplaceListing.objects
            .filter(status=MarketplaceListing.Status.ACTIVE)
            .select_related('seller__user', 'buyer__user', 'item')
        )
        serializer = MarketplaceListingSerializer(listings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        serializer = MarketplaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item_data = serializer.validated_data['item_data']
        price = serializer.validated_data['price']
        instance_id = item_data['instance_id']

        profile = PlayerProfileView._get_or_create_profile(request.user)

        with transaction.atomic():
            try:
                item = PlayerItem.objects.select_for_update().get(
                    owner=profile,
                    instance_id=instance_id,
                    state=PlayerItem.State.INVENTORY,
                )
            except PlayerItem.DoesNotExist:
                return Response(
                    {'detail': f'Item with instance_id "{instance_id}" not found in your inventory.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            item.state = PlayerItem.State.LISTED
            item.save(update_fields=['state', 'updated_at'])

            listing = MarketplaceListing.objects.create(
                seller=profile,
                item=item,
                price=price,
            )

        output = MarketplaceListingSerializer(listing).data
        return Response(output, status=status.HTTP_201_CREATED)


class MarketplaceDetailView(APIView):
    """
    DELETE /api/player/marketplace/<pk>/  — Cancel a listing (returns item to seller).
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, pk: int) -> Response:
        profile = PlayerProfileView._get_or_create_profile(request.user)

        try:
            listing = MarketplaceListing.objects.select_related('seller', 'item').get(pk=pk)
        except MarketplaceListing.DoesNotExist:
            return Response({'detail': 'Listing not found.'}, status=status.HTTP_404_NOT_FOUND)

        if listing.seller_id != profile.pk:
            return Response(
                {'detail': 'You can only cancel your own listings.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if listing.status != MarketplaceListing.Status.ACTIVE:
            return Response(
                {'detail': f'Cannot cancel a listing with status "{listing.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Return the item to the seller's inventory and mark cancelled atomically.
        with transaction.atomic():
            listing.status = MarketplaceListing.Status.CANCELLED
            listing.save(update_fields=['status', 'updated_at'])

            listing.item.owner = profile
            listing.item.state = PlayerItem.State.INVENTORY
            listing.item.save(update_fields=['owner', 'state', 'updated_at'])

        return Response(
            {'detail': 'Listing cancelled. Item returned to inventory.'},
            status=status.HTTP_200_OK,
        )


class MarketplacePurchaseView(APIView):
    """
    POST /api/player/marketplace/<pk>/buy/  — Purchase a listing.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk: int) -> Response:
        buyer_profile = PlayerProfileView._get_or_create_profile(request.user)

        with transaction.atomic():
            try:
                listing = (
                    MarketplaceListing.objects
                    .select_related('seller__user', 'item')
                    .select_for_update()
                    .get(pk=pk)
                )
            except MarketplaceListing.DoesNotExist:
                return Response({'detail': 'Listing not found.'}, status=status.HTTP_404_NOT_FOUND)

            if listing.status != MarketplaceListing.Status.ACTIVE:
                return Response(
                    {'detail': f'This listing is no longer available (status: {listing.status}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if listing.seller_id == buyer_profile.pk:
                return Response(
                    {'detail': 'You cannot purchase your own listing.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if buyer_profile.gold < listing.price:
                return Response(
                    {'detail': f'Insufficient gold. You have {buyer_profile.gold}, need {listing.price}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            seller_profile = listing.seller
            item = listing.item

            # Transfer gold: buyer pays, seller receives.
            buyer_profile.gold -= listing.price
            buyer_profile.save(update_fields=['gold', 'updated_at'])

            seller_profile.gold += listing.price
            seller_profile.save(update_fields=['gold', 'updated_at'])

            # Transfer item ownership to the buyer.
            item.owner = buyer_profile
            item.state = PlayerItem.State.INVENTORY
            item.save(update_fields=['owner', 'state', 'updated_at'])

            # Mark listing as sold.
            listing.status = MarketplaceListing.Status.SOLD
            listing.buyer = buyer_profile
            listing.save(update_fields=['status', 'buyer', 'updated_at'])

        return Response(
            {
                'detail': 'Purchase successful.',
                'gold_remaining': buyer_profile.gold,
                'item_data': serialize_item(item),
            },
            status=status.HTTP_200_OK,
        )
