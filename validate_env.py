"""
Environment variable validation and configuration checker.

Run this script to validate that all required environment variables
are properly configured before starting the application.
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_ENV_VARS = {
    'ENVIRONMENT': {
        'required': True,
        'description': 'Application environment (development/production)',
        'default': 'development',
        'valid_values': ['development', 'production', 'staging'],
    },
    'SECRET_KEY': {
        'required': True,
        'description': 'Django secret key for cryptographic operations',
        'default': None,
    },
    'DEBUG': {
        'required': False,
        'description': 'Enable debug mode (should be False in production)',
        'default': 'False',
        'valid_values': ['True', 'False'],
    },
    'ALLOWED_HOSTS': {
        'required': False,
        'description': 'Comma-separated list of allowed hosts',
        'default': 'localhost,127.0.0.1',
    },
}

OPTIONAL_ENV_VARS = {
    'TOKEN_TTL_SECONDS': {
        'description': 'Token expiration time in seconds',
        'default': '3600',
    },
    'DB_ENGINE': {
        'description': 'Database backend engine',
        'default': 'django.db.backends.postgresql',
    },
    'DB_NAME': {
        'description': 'Database name',
        'default': 'questfantasy',
    },
    'DB_USER': {
        'description': 'Database user',
        'default': 'postgres',
    },
    'DB_PASSWORD': {
        'description': 'Database password',
        'default': 'postgres',
    },
    'DB_HOST': {
        'description': 'Database host',
        'default': 'db',
    },
    'DB_PORT': {
        'description': 'Database port',
        'default': '5432',
    },
    'DJANGO_LOG_LEVEL': {
        'description': 'Django logging level',
        'default': 'INFO',
    },
}


def validate_environment():
    """Validate environment variables and print status.

    Returns:
        bool: True if all required variables are valid, False otherwise
    """
    print('=' * 60)
    print('Environment Variable Validator')
    print('=' * 60)

    errors = []
    warnings = []

    # Check required variables
    print('\nChecking REQUIRED variables:')
    print('-' * 40)
    for var_name, config in REQUIRED_ENV_VARS.items():
        value = os.getenv(var_name)

        if not value:
            if config['required']:
                errors.append(f"✗ {var_name}: NOT SET (required)")
                if config['default']:
                    print(f"  └─ Default: {config['default']}")
            continue

        # Check valid values if specified
        if 'valid_values' in config:
            if value not in config['valid_values']:
                errors.append(
                    f"✗ {var_name}: Invalid value '{value}'. "
                    f"Valid values: {', '.join(config['valid_values'])}"
                )
            else:
                print(f"✓ {var_name}: {value}")
        else:
            # Hide sensitive values
            display_value = '***' if var_name == 'SECRET_KEY' else value
            print(f"✓ {var_name}: {display_value}")

    # Check optional variables
    print('\nChecking OPTIONAL variables:')
    print('-' * 40)
    for var_name, config in OPTIONAL_ENV_VARS.items():
        value = os.getenv(var_name, config['default'])
        print(f"✓ {var_name}: {value} (using {'default' if not os.getenv(var_name) else 'configured'} value)")

    # Special checks for production
    environment = os.getenv('ENVIRONMENT', 'development')
    if environment == 'production':
        print('\nProduction-specific checks:')
        print('-' * 40)

        debug = os.getenv('DEBUG', 'False')
        if debug == 'True':
            errors.append("✗ DEBUG must be False in production")
        else:
            print("✓ DEBUG is disabled (correct for production)")

        secret_key = os.getenv('SECRET_KEY')
        if not secret_key or secret_key == 'dev-key':
            errors.append("✗ SECRET_KEY is not securely configured for production")
        else:
            print("✓ SECRET_KEY appears to be configured")

        allowed_hosts = os.getenv('ALLOWED_HOSTS')
        if allowed_hosts and '*' in allowed_hosts:
            errors.append("✗ ALLOWED_HOSTS contains '*' - not secure for production")
        elif allowed_hosts:
            print(f"✓ ALLOWED_HOSTS configured: {allowed_hosts}")

    # Print results
    print('\n' + '=' * 60)
    if errors:
        print(f'❌ VALIDATION FAILED ({len(errors)} error(s))')
        print('=' * 60)
        for error in errors:
            print(error)
        if warnings:
            print('\nWarnings:')
            for warning in warnings:
                print(f"⚠ {warning}")
        return False
    else:
        print('✅ VALIDATION PASSED')
        print('=' * 60)
        if warnings:
            print('\nWarnings:')
            for warning in warnings:
                print(f"⚠ {warning}")
        return True


if __name__ == '__main__':
    from dotenv import load_dotenv

    # Load .env file if it exists
    env_file = PROJECT_ROOT / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        print(f'Loaded environment from: {env_file}')
    else:
        print(f'Note: .env file not found at {env_file}')

    success = validate_environment()
    sys.exit(0 if success else 1)
