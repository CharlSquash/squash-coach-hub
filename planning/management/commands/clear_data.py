# planning/management/commands/clear_data.py
from django.core.management.base import BaseCommand
from planning.models import Player, SchoolGroup, ScheduledClass, Session

class Command(BaseCommand):
    help = 'Deletes all Players, SchoolGroups, ScheduledClasses, and Sessions from the database.'

    def handle(self, *args, **options):
        self.stdout.write("Deleting all session-related data...")
        Session.objects.all().delete()
        ScheduledClass.objects.all().delete()
        Player.objects.all().delete()
        SchoolGroup.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Successfully cleared data.'))