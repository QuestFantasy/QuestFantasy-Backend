from django.contrib import admin

from .models import PlayerProfile, PlayerSkill


class PlayerSkillInline(admin.TabularInline):
    model = PlayerSkill
    extra = 0


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'experience', 'hp_current', 'hp_max', 'gold', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'active_session_id', 'last_sequence')
    inlines = [PlayerSkillInline]
