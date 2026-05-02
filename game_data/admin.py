from django.contrib import admin

from .models import MarketplaceListing, PlayerItem, PlayerProfile, PlayerSkill


class PlayerSkillInline(admin.TabularInline):
    model = PlayerSkill
    extra = 0


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'experience', 'hp_current', 'hp_max', 'gold', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'active_session_id', 'last_sequence')
    inlines = [PlayerSkillInline]


@admin.register(PlayerItem)
class PlayerItemAdmin(admin.ModelAdmin):
    list_display = ('instance_id', 'owner', 'state', 'created_at', 'updated_at')
    list_filter = ('state',)
    search_fields = ('instance_id', 'owner__user__username', 'owner__user__email')
    readonly_fields = ('instance_id', 'created_at', 'updated_at')


@admin.register(MarketplaceListing)
class MarketplaceListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'seller', 'item', 'price', 'status', 'buyer', 'listed_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('seller__user__username', 'buyer__user__username')
    readonly_fields = ('listed_at', 'updated_at')
