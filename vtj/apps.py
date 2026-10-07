import logging

from django.apps import AppConfig
from django.conf import settings


class VtjConfig(AppConfig):
    name = "vtj"
    verbose_name = "VTJ integration"

    def ready(self) -> None:
        if settings.VTJ_MOCK_ENABLED:
            logging.getLogger("vety-guardian-portal-back").warning("VTJ_MOCK_ENABLED is on: serving mock VTJ data at /vtj-mock/api/HenkilonTunnuskysely")
