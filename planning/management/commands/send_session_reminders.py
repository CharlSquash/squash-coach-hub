# planning/management/commands/send_session_reminders.py

import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from planning.models import Session, Coach, CoachAvailability, User # Ensure User is imported
from planning.notifications import send_session_confirmation_email # Adjust path if needed

class Command(BaseCommand):
    help = 'Sends session confirmation email reminders to coaches for sessions occurring the next day.'

    # No add_arguments needed if we remove --run_type

    def handle(self, *args, **options):
        now_datetime = timezone.now() # Use timezone.now() for current aware datetime
        # It's good practice to ensure all date operations are consistent with timezone settings.
        # For calculating "tomorrow", using aware datetime's date part is fine.
        tomorrow_date = (now_datetime + datetime.timedelta(days=1)).date()

        self.stdout.write(f"[{now_datetime.strftime('%Y-%m-%d %H:%M:%S')}] Running send_session_reminders for sessions on: {tomorrow_date}")

        sessions_to_notify = Session.objects.filter(
            session_date=tomorrow_date,
            is_cancelled=False # Don't send reminders for cancelled sessions
        ).prefetch_related('coaches_attending', 'coaches_attending__user') # Prefetch user from Coach

        if not sessions_to_notify.exists():
            self.stdout.write(self.style.SUCCESS(f"No sessions scheduled for tomorrow ({tomorrow_date}) found for notification."))
            return

        notifications_sent = 0
        coaches_already_confirmed = 0
        sessions_processed = 0

        for session_obj in sessions_to_notify:
            sessions_processed += 1
            self.stdout.write(f"  Processing Session: {session_obj} on {session_obj.session_date} at {session_obj.session_start_time}")
            
            assigned_coaches = session_obj.coaches_attending.all()
            if not assigned_coaches:
                self.stdout.write(f"    No coaches assigned to this session. Skipping.")
                continue

            for coach_profile in assigned_coaches:
                coach_user = coach_profile.user # Assuming your Coach model has a 'user' ForeignKey to Django's User model
                
                if not coach_user:
                    self.stdout.write(self.style.WARNING(f"    Coach profile {coach_profile.name} (ID: {coach_profile.id}) has no linked user. Cannot send email."))
                    continue
                
                if not coach_user.email:
                    self.stdout.write(self.style.WARNING(f"    Coach {coach_user.username} has no email address. Skipping."))
                    continue

                # Check if coach has already confirmed for this session
                try:
                    availability = CoachAvailability.objects.get(
                        coach=coach_user, # CoachAvailability.coach links to User
                        session=session_obj
                    )
                    if availability.is_available:
                        self.stdout.write(f"    Coach {coach_user.username} has already confirmed for session {session_obj.id}. Skipping email.")
                        coaches_already_confirmed +=1
                        continue
                    # If availability.is_available is False (declined), still send.
                    # They might change their mind, or it reminds them of their declined status.
                    
                except CoachAvailability.DoesNotExist:
                    # No availability record yet, so definitely needs notification
                    pass
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"    Error checking availability for {coach_user.username} and session {session_obj.id}: {e}"))
                    continue

                self.stdout.write(f"    Attempting to send confirmation email to {coach_user.username} ({coach_user.email})...")
                email_sent_successfully = send_session_confirmation_email(coach_user, session_obj, is_reminder=False)
                
                if email_sent_successfully:
                    notifications_sent += 1
                else:
                    self.stderr.write(self.style.ERROR(f"    Failed to send email to {coach_user.username} for session {session_obj.id}."))

        self.stdout.write(self.style.SUCCESS(
            f"\nFinished sending session reminders for sessions on {tomorrow_date}."
            f"\nProcessed {sessions_processed} sessions."
            f"\nAttempted to send {notifications_sent} new email notifications."
            f"\nFound {coaches_already_confirmed} coaches already confirmed."
        ))
