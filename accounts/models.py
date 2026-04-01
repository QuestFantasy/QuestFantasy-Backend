"""
User-related models for QuestFantasy.

This module provides user profile and permission management models
that extend Django's built-in User model with additional functionality.
"""
from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """User profile model for storing extended user information.

    Attributes:
        user: One-to-one relationship with Django User model
        role: User role determining access level and permissions
        created_at: Timestamp when the profile was created
        updated_at: Timestamp when the profile was last updated
    """

    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('moderator', 'Moderator'),
        ('user', 'Regular User'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user',
        help_text='User role determining access level',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auth_user_profile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """Return string representation of user profile."""
        return f"{self.user.username} ({self.get_role_display()})"

    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == 'admin'

    def is_moderator(self) -> bool:
        """Check if user has moderator role."""
        return self.role == 'moderator'

    def is_regular_user(self) -> bool:
        """Check if user has regular user role."""
        return self.role == 'user'
