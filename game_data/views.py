from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PlayerProfile, PlayerSkill
from .serializers import (
    PlayerGoldSerializer,
    PlayerGoldUpdateSerializer,
    PlayerInventorySerializer,
    PlayerInventoryUpdateSerializer,
    PlayerProfileSerializer,
    PlayerProfileUpdateSerializer,
)


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
        session_id = validated.get('session_id')
        sequence = validated.get('sequence')

        if session_id:
            if profile.active_session_id != session_id:
                profile.active_session_id = session_id
                profile.last_sequence = 0

            if sequence is not None and sequence <= profile.last_sequence:
                current = PlayerProfileSerializer(profile).data
                current['ignored'] = True
                current['reason'] = 'stale_sequence'
                return Response(current, status=status.HTTP_200_OK)

        for field in (
            'level',
            'experience',
            'hp_max',
            'hp_current',
            'gold',
            'inventory_items',
            'discarded_items',
        ):
            if field in validated:
                setattr(profile, field, validated[field])

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

        if profile.hp_current > profile.hp_max:
            profile.hp_current = profile.hp_max

        if sequence is not None:
            profile.last_sequence = sequence

        profile.save()

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
        if 'inventory_items' in validated:
            profile.inventory_items = validated['inventory_items']

        if 'discarded_items' in validated:
            profile.discarded_items = validated['discarded_items']

        profile.save(update_fields=['inventory_items', 'discarded_items', 'updated_at'])
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
