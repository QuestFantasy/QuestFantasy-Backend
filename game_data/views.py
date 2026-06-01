from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MarketplaceListing, PlayerItem, PlayerProfile, PlayerSkill
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


def _sync_profile_items(profile: PlayerProfile, *, inventory_items=None, discarded_items=None) -> None:
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

        with transaction.atomic():
            session_id = validated.get('session_id')
            sequence   = validated.get('sequence')

            # Reset sequence counter when a new session starts.
            if session_id and profile.active_session_id != session_id:
                profile.active_session_id = session_id
                profile.last_sequence = 0

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
                )

            # Replace skills list.
            if 'skills' in validated:
                PlayerSkill.objects.filter(player_profile=profile).delete()
                for index, skill in enumerate(validated['skills']):
                    PlayerSkill.objects.create(
                        player_profile=profile,
                        skill_id=skill['skill_id'],
                        name=skill['name'],
                        cooldown_seconds=skill['cooldown_seconds'],
                        display_order=skill.get('display_order', index),
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

        profile.gold = serializer.validated_data['gold']
        profile.save(update_fields=['gold', 'updated_at'])

        output = PlayerGoldSerializer(profile).data
        return Response(output, status=status.HTTP_200_OK)


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
