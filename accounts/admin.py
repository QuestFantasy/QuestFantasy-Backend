"""Django admin configuration for accounts app."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for UserProfile model.

    Allows administrators to view and manage user profile information
    including roles and permissions.
    """

    list_display = ('user', 'role', 'created_at', 'updated_at')
    list_filter = ('role', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    fields = ('user', 'role', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        """Disable manual creation of UserProfile in admin.

        UserProfiles are automatically created via signals.
        """
        return False


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile in User admin."""

    model = UserProfile
    fields = ('role', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')


class CustomUserAdmin(BaseUserAdmin):
    """Enhanced User admin with inline UserProfile."""

    inlines = [UserProfileInline]


# Unregister default admin and register custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
