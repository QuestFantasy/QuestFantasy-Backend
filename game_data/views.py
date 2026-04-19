from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PlayerProfile, PlayerSkill
from .serializers import PlayerProfileSerializer, PlayerProfileUpdateSerializer


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

        for field in ('level', 'experience', 'hp_max', 'hp_current', 'gold'):
            if field in validated:
                setattr(profile, field, validated[field])

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
            PlayerSkill.objects.create(
                player_profile=profile,
                skill_id='basic_attack',
                name='Basic Attack',
                cooldown_seconds=1.0,
                display_order=0,
            )
        return profile
