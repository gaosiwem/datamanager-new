from haystack.management.commands.update_index import Command as HaystackUpdateIndexCommand


class Command(HaystackUpdateIndexCommand):
    """
    Prefer Haystack's update_index command over Wagtail's command.

    Django resolves management command names across installed apps, and this
    project includes both Wagtail and Haystack. The portal search rebuild flow
    relies on Haystack's legacy option set, so we explicitly shadow Wagtail's
    update_index command here.
    """

    pass
