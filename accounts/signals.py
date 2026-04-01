"""
Signal handlers for user model events.

This module provides signal handlers that respond to user creation
events, automatically creating associated UserProfile instances.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .models import UserProfile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when a new User is created.

    Args:
        sender: The model class (User)
        instance: The user instance being saved
        created: Boolean flag indicating if this is a new object
        **kwargs: Additional keyword arguments
    """
    if created:
        UserProfile.objects.create(user=instance)
        logger.info(f'UserProfile created for user {instance.username}')


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when a User is saved.

    Args:
        sender: The model class (User)
        instance: The user instance being saved
        **kwargs: Additional keyword arguments
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()
