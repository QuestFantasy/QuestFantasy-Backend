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
