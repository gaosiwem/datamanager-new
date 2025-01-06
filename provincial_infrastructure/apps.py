from django.apps import AppConfig


class ProvincialInfrastructureConfig(AppConfig):
    name = "provincial_infrastructure"
    verbose_name = "Provincial Infrastructuress"

    def ready(self):
        import provincial_infrastructure.signals  # noqa
