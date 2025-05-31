import sys

from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'App'

    def ready(self):
        if 'runserver' in sys.argv:
            from . import scheduler
            scheduler.start()
