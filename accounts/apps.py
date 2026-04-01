"""Application configuration for accounts app."""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration class for accounts application.

    Handles initialization of signals and other app-level
    configuration for user authentication and management.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self) -> None:
        """Initialize app-level configuration.

        Called when Django starts. Imports signal handlers to ensure
        they are registered when the app is ready.
        """
        import accounts.signals  # noqa: F401

