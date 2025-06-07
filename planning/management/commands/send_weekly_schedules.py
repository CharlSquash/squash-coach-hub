# planning/management/commands/send_weekly_schedules.py

import calendar
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from planning.models import Coach, Session
from planning.notifications import send_weekly_schedule_email

class Command(BaseCommand):
    help = 'Sends each opted-in coach an email with their schedule for the upcoming week (Mon-Sun).'

    def handle(self, *args, **options):
        self.stdout.write("Starting to send weekly schedule emails...")

        # --- 1. Determine the date range for the upcoming week (Monday to Sunday) ---
        today = timezone.now().date()
        # weekday() returns 0 for Monday, 1 for Tuesday, ..., 6 for Sunday.
        # We want to find the NEXT Monday.
        days_until_monday = (0 - today.weekday() + 7) % 7
        if days_until_monday == 0: # If today is Monday, we want next week's Monday
            days_until_monday = 7
            
        upcoming_monday = today + timedelta(days=days_until_monday)
        upcoming_sunday = upcoming_monday + timedelta(days=6)

        self.stdout.write(f"Fetching schedules for the week of: {upcoming_monday.strftime('%Y-%m-%d')} to {upcoming_sunday.strftime('%Y-%m-%d')}")

        # --- 2. Get all active, opted-in coaches with an email address ---
        coaches_to_email = Coach.objects.filter(
            is_active=True,
            receive_weekly_schedule_email=True,
            user__email__isnull=False
        ).exclude(
            user__email__exact=''
        ).select_related('user')

        sent_email_count = 0
        for coach in coaches_to_email:
            # --- 3. For each coach, find their assigned sessions for the upcoming week ---
            sessions_for_coach = Session.objects.filter(
                coaches_attending=coach,
                session_date__gte=upcoming_monday,
                session_date__lte=upcoming_sunday,
                is_cancelled=False
            ).select_related('school_group', 'venue').prefetch_related('coaches_attending')

            if not sessions_for_coach.exists():
                # As requested, skip sending an email if the coach has no sessions
                self.stdout.write(f"  Coach {coach.name} has no sessions this week. Skipping.")
                continue

            # --- 4. Group the sessions by day for the email template ---
            sessions_by_day = []
            day_names = list(calendar.day_name)
            
            # Initialize a dictionary to hold sessions for each day of the week
            daily_sessions_dict = {day_names[i]: [] for i in range(7)}

            for session in sessions_for_coach:
                day_name = session.session_date.strftime('%A')
                
                # Find other coaches on the same session
                other_coaches = [c.name for c in session.coaches_attending.all() if c.id != coach.id]
                session.other_coaches = other_coaches # Attach this list to the session object for the template
                
                daily_sessions_dict[day_name].append(session)

            # Create the final list structure the template expects
            for i in range(7): # Loop Monday to Sunday
                 day_name = day_names[i]
                 if daily_sessions_dict[day_name]:
                     sessions_by_day.append({
                         'day_name': day_name,
                         'date': upcoming_monday + timedelta(days=i),
                         'sessions': daily_sessions_dict[day_name]
                     })

            # --- 5. Send the email ---
            try:
                send_weekly_schedule_email(
                    coach_user=coach.user,
                    week_start_date=upcoming_monday,
                    sessions_by_day=sessions_by_day
                )
                sent_email_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Failed to send email to {coach.name}. Error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"--- Process complete. Sent {sent_email_count} weekly schedule emails. ---"))