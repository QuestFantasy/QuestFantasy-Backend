from django.contrib.auth import get_user_model
from django.db import models


User = get_user_model()


class PlayerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='player_profile',
    )
    level = models.PositiveIntegerField(default=1)
    experience = models.PositiveIntegerField(default=0)
    hp_max = models.PositiveIntegerField(default=100)
    hp_current = models.PositiveIntegerField(default=100)
    gold = models.PositiveIntegerField(default=0)

    # Inventory sync payloads from the game client.
    # Stored as list of item snapshots (dicts). Structure is owned by the client.
    inventory_items = models.JSONField(default=list, blank=True)

    # Items the player discarded/dropped. Kept for audit/analytics and potential restore.
    discarded_items = models.JSONField(default=list, blank=True)

    # Idempotent client sync metadata.
    active_session_id = models.CharField(max_length=64, blank=True, default='')
    last_sequence = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'player_profile'
        ordering = ['user_id']

    def __str__(self) -> str:
        return f"{self.user.username} L{self.level} HP {self.hp_current}/{self.hp_max}"


class PlayerSkill(models.Model):
    player_profile = models.ForeignKey(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name='skills',
    )
    skill_id = models.CharField(max_length=64)
    name = models.CharField(max_length=120)
    cooldown_seconds = models.FloatField(default=1.0)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'player_skill'
        ordering = ['display_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['player_profile', 'skill_id'],
                name='uniq_player_skill_id',
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player_profile.user.username}:{self.skill_id}"
