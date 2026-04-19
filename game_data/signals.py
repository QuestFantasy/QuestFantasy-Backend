from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PlayerProfile, PlayerSkill


User = get_user_model()


@receiver(post_save, sender=User)
def create_player_profile(sender, instance, created, **kwargs):
    if not created:
        return

    profile = PlayerProfile.objects.create(user=instance)
    PlayerSkill.objects.create(
        player_profile=profile,
        skill_id='basic_attack',
        name='Basic Attack',
        cooldown_seconds=1.0,
        display_order=0,
    )
