from django.core.management.base import BaseCommand

from budgetportal.assistant.document_ingestion import sync_all_application_content


class Command(BaseCommand):
    help = "Backfill approved Vulekamali FAQs, glossary, guides, and portal pages for the AI assistant."

    def handle(self, *args, **options):
        counts = sync_all_application_content()
        self.stdout.write(
            self.style.SUCCESS(
                "Assistant content synchronised: FAQs={faq}, guides={guide}, "
                "portal pages={portal_page}, about page={about}, glossary terms={glossary}.".format(**counts)
            )
        )
