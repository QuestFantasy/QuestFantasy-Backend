import uuid

from rest_framework import serializers

from .models import MarketplaceListing, PlayerItem, PlayerProfile, PlayerSkill


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def ensure_instance_ids(items: list) -> tuple[list, bool]:
    """
    Iterate over a list of item dicts.  Any item that is missing an
    ``instance_id`` key (or whose value is empty/None) is assigned a new
    UUID4 string in-place.

    Returns:
        (items, changed)  where ``changed`` is True when at least one item
        was mutated so the caller knows to save the updated list.
    """
    changed = False
    seen_instance_ids = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        instance_id = item.get('instance_id')
        if not instance_id:
            instance_id = str(uuid.uuid4())
            item['instance_id'] = instance_id
            changed = True
        else:
            try:
                instance_id = str(uuid.UUID(str(instance_id)))
            except (TypeError, ValueError):
                raise serializers.ValidationError('instance_id must be a valid UUID.')
            item['instance_id'] = instance_id

        if instance_id in seen_instance_ids:
            raise serializers.ValidationError('Duplicate instance_id values are not allowed.')
        seen_instance_ids.add(instance_id)
    return items, changed


def serialize_item(item: PlayerItem) -> dict:
    payload = dict(item.item_data or {})
    payload['instance_id'] = str(item.instance_id)
    return payload


# ---------------------------------------------------------------------------
# Player profile / skill serializers
# ---------------------------------------------------------------------------

class PlayerSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerSkill
        fields = ('skill_id', 'name', 'cooldown_seconds', 'display_order')


class PlayerProfileSerializer(serializers.ModelSerializer):
    skills = serializers.SerializerMethodField()
    inventory_items = serializers.SerializerMethodField()
    discarded_items = serializers.SerializerMethodField()

    class Meta:
        model = PlayerProfile
        fields = (
            'level',
            'experience',
            'hp_max',
            'hp_current',
            'gold',
            'class_name',
            'inventory_items',
            'discarded_items',
            'equipped_items',
            'skills',
            'updated_at',
        )

    def get_skills(self, obj):
        ordered_skills = obj.skills.all().order_by('display_order', 'id')
        return PlayerSkillSerializer(ordered_skills, many=True).data

    def get_inventory_items(self, obj):
        items = obj.items.filter(state=PlayerItem.State.INVENTORY).order_by('id')
        return [serialize_item(item) for item in items]

    def get_discarded_items(self, obj):
        items = obj.items.filter(state=PlayerItem.State.DISCARDED).order_by('id')
        return [serialize_item(item) for item in items]


class PlayerProfileUpdateSerializer(serializers.Serializer):
    level = serializers.IntegerField(required=False, min_value=1)
    experience = serializers.IntegerField(required=False, min_value=0)
    hp_max = serializers.IntegerField(required=False, min_value=1)
    hp_current = serializers.IntegerField(required=False, min_value=0)
    gold = serializers.IntegerField(required=False, min_value=0)
    class_name = serializers.ChoiceField(
        choices=[c[0] for c in PlayerProfile.CLASS_CHOICES],
        required=False,
    )
    skills = PlayerSkillSerializer(many=True, required=False)
    inventory_items = serializers.ListField(
        child=serializers.DictField(),
        required=False,
    )
    discarded_items = serializers.ListField(
        child=serializers.DictField(),
        required=False,
    )
    equipped_items = serializers.DictField(
        required=False,
    )

    # Idempotency metadata.
    session_id = serializers.CharField(required=False, allow_blank=False, max_length=64)
    sequence = serializers.IntegerField(required=False, min_value=0)

    # Secure drop claims
    claimed_drops = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )

    def validate(self, attrs):
        hp_max = attrs.get('hp_max')
        hp_current = attrs.get('hp_current')

        if hp_max is not None and hp_current is not None and hp_current > hp_max:
            raise serializers.ValidationError({'hp_current': 'hp_current cannot exceed hp_max.'})

        # Validate that skill_ids are unique within the provided skills list.
        skills = attrs.get('skills')
        if skills is not None:
            skill_ids = set()
            for skill in skills:
                skill_id = skill.get('skill_id')
                if skill_id in skill_ids:
                    raise serializers.ValidationError({'skills': 'Duplicate skill_id values are not allowed.'})
                skill_ids.add(skill_id)

        return attrs


class PlayerInventorySerializer(serializers.ModelSerializer):
    inventory_items = serializers.SerializerMethodField()
    discarded_items = serializers.SerializerMethodField()

    class Meta:
        model = PlayerProfile
        fields = (
            'inventory_items',
            'discarded_items',
            'equipped_items',
            'updated_at',
        )

    def get_inventory_items(self, obj):
        items = obj.items.filter(state=PlayerItem.State.INVENTORY).order_by('id')
        return [serialize_item(item) for item in items]

    def get_discarded_items(self, obj):
        items = obj.items.filter(state=PlayerItem.State.DISCARDED).order_by('id')
        return [serialize_item(item) for item in items]


class PlayerInventoryUpdateSerializer(serializers.Serializer):
    inventory_items = serializers.ListField(
        child=serializers.DictField(),
        required=False,
    )
    discarded_items = serializers.ListField(
        child=serializers.DictField(),
        required=False,
    )
    equipped_items = serializers.DictField(
        required=False,
    )


class PlayerGoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerProfile
        fields = (
            'gold',
            'updated_at',
        )


class PlayerGoldUpdateSerializer(serializers.Serializer):
    gold = serializers.IntegerField(required=True, min_value=0)


# ---------------------------------------------------------------------------
# Marketplace serializers
# ---------------------------------------------------------------------------

class MarketplaceListingSerializer(serializers.ModelSerializer):
    seller_username = serializers.CharField(source='seller.user.username', read_only=True)
    buyer_username = serializers.SerializerMethodField()
    item_data = serializers.SerializerMethodField()

    class Meta:
        model = MarketplaceListing
        fields = (
            'id',
            'seller_username',
            'item_data',
            'price',
            'status',
            'buyer_username',
            'listed_at',
            'updated_at',
        )

    def get_buyer_username(self, obj):
        return obj.buyer.user.username if obj.buyer else None

    def get_item_data(self, obj):
        return serialize_item(obj.item)


class MarketplaceCreateSerializer(serializers.Serializer):
    item_data = serializers.DictField()
    price = serializers.IntegerField(min_value=1)

    def validate_item_data(self, value):
        if not value.get('instance_id'):
            raise serializers.ValidationError(
                'item_data must include a non-empty instance_id. '
                'Sync your inventory first so the backend assigns IDs.'
            )
        try:
            value['instance_id'] = str(uuid.UUID(str(value['instance_id'])))
        except (TypeError, ValueError):
            raise serializers.ValidationError('item_data.instance_id must be a valid UUID.')
        return value
