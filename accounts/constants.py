"""Application-wide constants."""

# User Roles
USER_ROLE_ADMIN = 'admin'
USER_ROLE_MODERATOR = 'moderator'
USER_ROLE_USER = 'user'

USER_ROLES = [
    (USER_ROLE_ADMIN, 'Administrator'),
    (USER_ROLE_MODERATOR, 'Moderator'),
    (USER_ROLE_USER, 'Regular User'),
]

# Default values
DEFAULT_TOKEN_TTL_SECONDS = 3600
DEFAULT_PAGE_SIZE = 50

# Rate Limiting
ANONYMOUS_RATE_LIMIT = '100/hour'
AUTHENTICATED_RATE_LIMIT = '1000/hour'

# Password validation
MIN_PASSWORD_LENGTH = 8

# Response messages
MESSAGES = {
    'REGISTRATION_SUCCESS': 'Registration successful.',
    'LOGIN_SUCCESS': 'Login successful.',
    'LOGOUT_SUCCESS': 'Logout successful.',
    'INVALID_CREDENTIALS': 'Invalid credentials.',
    'TOKEN_EXPIRED': 'Token has expired. Please login again.',
    'EMAIL_ALREADY_EXISTS': 'This email is already in use.',
    'USERNAME_ALREADY_EXISTS': 'This username is already in use.',
    'PASSWORD_MISMATCH': 'Passwords do not match.',
    'INVALID_TOKEN': 'Invalid authentication token.',
    'AUTHENTICATION_REQUIRED': 'Authentication credentials were not provided.',
}
