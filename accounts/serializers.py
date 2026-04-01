"""
Serializers for user authentication endpoints.

This module provides serializers for user registration, login, and profile management,
including validation of user input and sanitization of output data.
"""
from typing import Dict, Any

from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration.

    Validates and creates new user accounts with password confirmation.
    Ensures email uniqueness and password strength.

    Attributes:
        password: Write-only password field with minimum length validation
        confirm_password: Write-only field for password confirmation
    """

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        help_text='Password must be at least 8 characters long',
    )
    confirm_password = serializers.CharField(
        write_only=True,
        min_length=8,
        help_text='Password confirmation must match password field',
    )

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'confirm_password')
        read_only_fields = ('id',)

    def validate_email(self, value: str) -> str:
        """Validate that email is unique and properly formatted.

        Args:
            value: Email address to validate

        Returns:
            Normalized email address (lowercase and stripped)

        Raises:
            serializers.ValidationError: If email already exists
        """
        email = value.lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('This email is already in use.')
        return email

    def validate_username(self, value: str) -> str:
        """Validate that username is unique.

        Args:
            value: Username to validate

        Returns:
            Username

        Raises:
            serializers.ValidationError: If username already exists
        """
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already in use.')
        return value

    def validate_password(self, value: str) -> str:
        """Validate password strength using Django's password validators.

        Args:
            value: Password to validate

        Returns:
            Password

        Raises:
            serializers.ValidationError: If password is too weak
        """
        try:
            password_validation.validate_password(value)
        except password_validation.ValidationError as e:
            raise serializers.ValidationError(str(e))
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-field validation for password confirmation.

        Args:
            attrs: Dictionary of field values

        Returns:
            Validated attributes

        Raises:
            serializers.ValidationError: If passwords don't match
        """
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')

        if password != confirm_password:
            raise serializers.ValidationError(
                {'confirm_password': 'Passwords do not match.'},
            )

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> User:
        """Create a new user with validated data.

        Args:
            validated_data: Validated user data

        Returns:
            Created User instance
        """
        validated_data.pop('confirm_password', None)
        # Normalize email during creation
        validated_data['email'] = validated_data.get('email', '').lower().strip()
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    """Serializer for user login.

    Accepts either username or email (but not both) along with password.
    Validates that at least one credential type is provided.

    Attributes:
        username: Optional username for login
        email: Optional email for login
        password: Password field (write-only)
    """

    username = serializers.CharField(
        required=False,
        allow_blank=False,
        help_text='Username for login (alternative to email)',
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=False,
        help_text='Email for login (alternative to username)',
    )
    password = serializers.CharField(
        write_only=True,
        help_text='User password',
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that exactly one of username or email is provided.

        Args:
            attrs: Dictionary of field values

        Returns:
            Validated attributes

        Raises:
            serializers.ValidationError: If wrong number of credentials provided
        """
        username = attrs.get('username')
        email = attrs.get('email')

        if not username and not email:
            raise serializers.ValidationError(
                'Provide either username or email.',
            )

        if username and email:
            raise serializers.ValidationError(
                'Provide only one of username or email.',
            )

        return attrs


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for user details (read-only for profile view).

    Exposes only safe user information without sensitive data.

    Attributes:
        role: User role from UserProfile (read-only)
    """

    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role')
        read_only_fields = ('id', 'username', 'email', 'role')

    def get_role(self, obj: User) -> str:
        """Get user role from their profile.

        Args:
            obj: User instance

        Returns:
            User role or 'user' if profile doesn't exist
        """
        if hasattr(obj, 'profile'):
            return obj.profile.get_role_display()
        return 'user'

