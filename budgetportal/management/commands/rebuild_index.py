from django.core.management import call_command
from haystack.management.commands.rebuild_index import Command as HaystackRebuildIndexCommand


class Command(HaystackRebuildIndexCommand):
    """
    Route rebuilds through Haystack's update command explicitly.

    Wagtail also exposes an `update_index` management command, and Django
    resolves that name before Haystack in this project. Haystack's stock
    `rebuild_index` command delegates to `update_index`, which causes option
    mismatches. We keep Haystack's CLI surface here, but call the Haystack
    update alias directly.
    """

    def handle(self, **options):
        clear_options = options.copy()
        update_options = options.copy()

        for key in ("batchsize", "workers"):
            clear_options.pop(key, None)

        update_options.pop("interactive", None)

        call_command("clear_index", **clear_options)
        call_command("haystack_update_index", **update_options)
