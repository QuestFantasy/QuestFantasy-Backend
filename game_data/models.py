import uuid

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
    gold = models.PositiveIntegerField(default=100)

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


class PlayerItem(models.Model):
    class State(models.TextChoices):
        INVENTORY = 'inventory', 'Inventory'
        DISCARDED = 'discarded', 'Discarded'
        LISTED = 'listed', 'Listed'

    owner = models.ForeignKey(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name='items',
    )
    instance_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    item_data = models.JSONField(default=dict)
    state = models.CharField(
        max_length=16,
        choices=State.choices,
        default=State.INVENTORY,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'player_item'
        ordering = ['id']

    def __str__(self) -> str:
        return f"{self.owner.user.username}:{self.instance_id}"


class MarketplaceListing(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SOLD = 'sold', 'Sold'
        CANCELLED = 'cancelled', 'Cancelled'

    seller = models.ForeignKey(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name='marketplace_listings',
    )
    item = models.ForeignKey(
        PlayerItem,
        on_delete=models.PROTECT,
        related_name='marketplace_listings',
    )
    price = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    buyer = models.ForeignKey(
        PlayerProfile,
        on_delete=models.SET_NULL,
        related_name='marketplace_purchases',
        null=True,
        blank=True,
    )
    listed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marketplace_listing'
        ordering = ['-listed_at']

    def __str__(self) -> str:
        return f"Listing {self.pk} {self.status} {self.price}"
