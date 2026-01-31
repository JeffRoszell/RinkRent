from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import IceSurface
from bookings.services import generate_slots_for_surface


class Command(BaseCommand):
    help = "Generate bookable slots for all ice surfaces for the next N days (default 28)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=28,
            help="Number of days ahead to generate slots (default 28).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        start = timezone.now()
        end = start + timedelta(days=days)
        total = 0
        for surface in IceSurface.objects.all():
            created = generate_slots_for_surface(surface, start, end)
            total += len(created)
            if created:
                self.stdout.write(self.style.SUCCESS(f"{surface}: created {len(created)} slots"))
        self.stdout.write(self.style.SUCCESS(f"Total slots created: {total}"))
