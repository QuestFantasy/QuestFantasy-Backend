from django.apps import AppConfig


class GameDataConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'game_data'

    def ready(self) -> None:
        import game_data.signals  # noqa: F401
