# planning/notifications.py

import datetime
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.utils.html import strip_tags
from datetime import timedelta
from django.contrib.auth import get_user_model

from planning.models import Session, CoachAvailability  # your models

User = get_user_model() # <<< AND THIS


# Initialize a TimestampSigner for session confirmations
confirmation_signer = TimestampSigner(salt='planning.session_confirmation')


def send_session_confirmation_email(coach_user, session_obj, is_reminder=False):
    """
    Sends an email to a coach to confirm their attendance for an upcoming session.
    """
    if not coach_user.email:
        print(f"Cannot send confirmation email: Coach user {coach_user.username} has no email address.")
        return False

    token_payload = f"{coach_user.id}:{session_obj.id}"
    signed_token = confirmation_signer.sign(token_payload)

    SITE_URL = getattr(settings, 'APP_SITE_URL', 'http://127.0.0.1:8000')

    confirm_path = reverse('planning:confirm_session_attendance', args=[session_obj.id, signed_token])
    decline_path = reverse('planning:decline_session_attendance', args=[session_obj.id, signed_token])

    confirm_url = f"{SITE_URL}{confirm_path}"
    decline_url = f"{SITE_URL}{decline_path}"

    subject_prefix = "REMINDER: " if is_reminder else ""
    subject = (
        f"{subject_prefix}Session Confirmation Required: "
        f"{session_obj.school_group.name if session_obj.school_group else 'Session'} "
        f"on {session_obj.session_date.strftime('%a, %d %b %Y')}"
    )

    context = {
        'coach_name': coach_user.first_name or coach_user.username,
        'session_date': session_obj.session_date.strftime('%A, %d %B %Y'),
        'session_time': session_obj.session_start_time.strftime('%H:%M'),
        'session_group': session_obj.school_group.name if session_obj.school_group else "N/A",
        'session_venue': session_obj.venue.name if session_obj.venue else "N/A",
        'confirm_url': confirm_url,
        'decline_url': decline_url,
        'is_reminder': is_reminder,
        'site_name': "SquashSync",
    }

    html_message = render_to_string('planning/emails/session_confirmation_email.html', context)
    plain_message = strip_tags(html_message)
    from_email = settings.DEFAULT_FROM_EMAIL

    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [coach_user.email],
            html_message=html_message
        )
        print(f"Sent session confirmation email to {coach_user.email} for session {session_obj.id}. Reminder: {is_reminder}")
        return True
    except Exception as e:
        print(f"Error sending session confirmation email to {coach_user.email}: {e}")
        return False


def verify_confirmation_token(token):
    """
    Verifies a signed token (with timestamp) and returns the payload.
    Returns None if the token is invalid or expired.
    """
    try:
        payload = confirmation_signer.unsign(token, max_age=timedelta(days=7))
        return payload
    except (BadSignature, SignatureExpired):
        print("Token verification failed: Invalid, tampered, or expired token.")
        return None
    except Exception as e:
        print(f"Unexpected error during token verification: {e}")
        return None

def send_availability_change_alert_to_admins(session, coach, reason):
    """
    Sends an email alert to all superusers when an assigned coach
    marks themselves as unavailable for an upcoming session.
    """
    # Find all superusers to notify
    admin_users = User.objects.filter(is_superuser=True, is_active=True)
    
    # Get a list of their email addresses, filtering out any who don't have one
    admin_emails = [user.email for user in admin_users if user.email]

    if not admin_emails:
        print("ADMIN ALERT: No admin emails found to send cancellation notification.")
        return # Exit if no admin emails are configured

    subject = f"[SquashSync ALERT] Coach Availability Change for Session on {session.session_date.strftime('%a, %d %b')}"
    
    context = {
        'coach': coach,
        'session': session,
        'reason': reason,
        'site_url': settings.APP_SITE_URL, # Assumes APP_SITE_URL is in your settings
        'staffing_page_url': reverse('planning:session_staffing'),
    }

    html_message = render_to_string('planning/emails/availability_change_alert.html', context)
    plain_text_message = (
        f"Coach Availability Change Alert\n\n"
        f"Coach: {coach.name or coach.user.username}\n"
        f"Has marked themselves as UNAVAILABLE for an assigned session.\n\n"
        f"Session Details:\n"
        f"  Group: {session.school_group.name if session.school_group else 'N/A'}\n"
        f"  Date: {session.session_date.strftime('%A, %d %B %Y')}\n"
        f"  Time: {session.session_start_time.strftime('%H:%M')}\n\n"
        f"Reason Provided:\n{reason}\n\n"
        f"Please review the session staffing here: {settings.APP_SITE_URL}{reverse('planning:session_staffing')}\n"
    )

    try:
        send_mail(
            subject,
            plain_text_message,
            settings.DEFAULT_FROM_EMAIL, # Your sender email
            admin_emails, # List of recipients
            html_message=html_message,
            fail_silently=False,
        )
        print(f"Successfully sent cancellation alert to {len(admin_emails)} admin(s) for session {session.id}.")
    except Exception as e:
        # Log the error if sending fails
        print(f"ERROR: Could not send cancellation alert email. Error: {e}")

def send_weekly_schedule_email(coach_user, week_start_date, sessions_by_day):
    """
    Sends a coach their personalized session schedule for the upcoming week.
    """
    if not coach_user.email:
        print(f"Cannot send weekly schedule: Coach user {coach_user.username} has no email address.")
        return False

    week_end_date = week_start_date + timedelta(days=6)
    
    subject = f"Your SquashSync Schedule for {week_start_date.strftime('%d %b')} - {week_end_date.strftime('%d %b %Y')}"

    # We build the full URL to the calendar in the context
    calendar_url = f"{settings.APP_SITE_URL}{reverse('planning:session_calendar')}"

    context = {
        'coach_name': coach_user.first_name or coach_user.username,
        'week_start_date': week_start_date,
        'week_end_date': week_end_date,
        'sessions_by_day': sessions_by_day,
        'calendar_url': calendar_url,
        'site_name': "SquashSync",
    }

    html_message = render_to_string('planning/emails/weekly_schedule_email.html', context)
    plain_message = strip_tags(html_message) # Basic plain text version
    from_email = settings.DEFAULT_FROM_EMAIL

    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [coach_user.email],
            html_message=html_message,
            fail_silently=False
        )
        print(f"Sent weekly schedule email to {coach_user.email}")
        return True
    except Exception as e:
        print(f"Error sending weekly schedule email to {coach_user.email}: {e}")
        return False
