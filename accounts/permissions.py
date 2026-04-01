"""Custom permission classes for API access control."""
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import UserProfile


class IsAdmin(permissions.BasePermission):
    """Permission to check if user has admin role."""

    message = 'Only administrators can access this resource.'

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Check if user is an admin.

        Args:
            request: The current request
            view: The view being accessed

        Returns:
            True if user is authenticated and has admin role
        """
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request.user, 'profile'):
            return False

        return request.user.profile.is_admin()


class IsModerator(permissions.BasePermission):
    """Permission to check if user has moderator role or higher."""

    message = 'Only moderators and administrators can access this resource.'

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Check if user is moderator or admin.

        Args:
            request: The current request
            view: The view being accessed

        Returns:
            True if user is authenticated and has moderator/admin role
        """
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(request.user, 'profile'):
            return False

        return request.user.profile.role in ['admin', 'moderator']


class IsRegularUser(permissions.BasePermission):
    """Permission to check if user has at least regular user role."""

    message = 'You must have a valid user account to access this resource.'

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Check if user is authenticated.

        Args:
            request: The current request
            view: The view being accessed

        Returns:
            True if user is authenticated
        """
        return bool(request.user and request.user.is_authenticated)


class IsUserOwner(permissions.BasePermission):
    """Permission to check if user is the owner of the resource.

    Expected to be used with object-level permission checking.
    """

    message = 'You can only access your own data.'

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        """Check if user owns the object.

        Args:
            request: The current request
            view: The view being accessed
            obj: The object being accessed

        Returns:
            True if user is the owner or is an admin
        """
        # Assume obj has a 'user' field
        if hasattr(obj, 'user'):
            if request.user == obj.user:
                return True

        # Admins can access everything
        if hasattr(request.user, 'profile') and request.user.profile.is_admin():
            return True

        return False
