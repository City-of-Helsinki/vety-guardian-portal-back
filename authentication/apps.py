from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    name = "authentication"

    def ready(self):
        from . import schema  # noqa: F401  registers the OpenAPI auth extension
        from .jwt_leeway import install

        install()
