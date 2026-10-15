from django.core.management.base import BaseCommand

from agents.tasks import run_scheduled_agents_task


class Command(BaseCommand):
    help = "Queue a run for every active daily agent (same as the 08:00 beat job). Handy for demos."

    def handle(self, *args, **options):
        result = run_scheduled_agents_task.delay()
        self.stdout.write(self.style.SUCCESS(f"Queued run_scheduled_agents_task ({result.id})"))
