from rest_framework import serializers

from .models import PlayerProfile, PlayerSkill


class PlayerSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerSkill
        fields = ('skill_id', 'name', 'cooldown_seconds', 'display_order')


class PlayerProfileSerializer(serializers.ModelSerializer):
    skills = PlayerSkillSerializer(many=True, read_only=True)

    class Meta:
        model = PlayerProfile
        fields = (
            'level',
            'experience',
            'hp_max',
            'hp_current',
            'gold',
            'skills',
            'updated_at',
        )


class PlayerProfileUpdateSerializer(serializers.Serializer):
    level = serializers.IntegerField(required=False, min_value=1)
    experience = serializers.IntegerField(required=False, min_value=0)
    hp_max = serializers.IntegerField(required=False, min_value=1)
    hp_current = serializers.IntegerField(required=False, min_value=0)
    gold = serializers.IntegerField(required=False, min_value=0)
    skills = PlayerSkillSerializer(many=True, required=False)

    # Idempotency metadata.
    session_id = serializers.CharField(required=False, allow_blank=False, max_length=64)
    sequence = serializers.IntegerField(required=False, min_value=0)

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
