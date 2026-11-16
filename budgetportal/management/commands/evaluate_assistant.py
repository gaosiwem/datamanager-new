import json

from django.core.management.base import BaseCommand, CommandError

from budgetportal.assistant.evaluation import evaluate, load_json


class Command(BaseCommand):
    help = "Calculate Vulekamali assistant golden-question evaluation metrics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture", default="budgetportal/tests/fixtures/golden_questions.json"
        )
        parser.add_argument(
            "--results", required=True, help="JSON list of recorded assistant outputs"
        )

    def handle(self, *args, **options):
        try:
            metrics = evaluate(
                load_json(options["fixture"]), load_json(options["results"])
            )
        except (OSError, ValueError, KeyError) as error:
            raise CommandError("Could not evaluate assistant results.")
        self.stdout.write(json.dumps(metrics, indent=2, sort_keys=True))
