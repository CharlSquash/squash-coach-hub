# planning/notifications.py (or planning/utils.py)

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings
# MODIFIED: Use TimestampSigner and import SignatureExpired
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired 
from django.utils.html import strip_tags
from datetime import timedelta # Ensure timedelta is imported

# MODIFIED: Initialize a TimestampSigner
confirmation_signer = TimestampSigner(salt='planning.session_confirmation')

def send_session_confirmation_email(coach_user, session_obj, is_reminder=False):
    """
    Sends an email to a coach to confirm their attendance for an upcoming session.
    """
    if not coach_user.email:
        print(f"Cannot send confirmation email: Coach user {coach_user.username} has no email address.")
        return False

    token_payload = f"{coach_user.id}:{session_obj.id}"
    signed_token = confirmation_signer.sign(token_payload) # Signer now includes a timestamp

    SITE_URL = getattr(settings, 'APP_SITE_URL', 'http://127.0.0.1:8000') 

    confirm_path = reverse('planning:confirm_session_attendance', args=[session_obj.id, signed_token])
    decline_path = reverse('planning:decline_session_attendance', args=[session_obj.id, signed_token])

    confirm_url = f"{SITE_URL}{confirm_path}"
    decline_url = f"{SITE_URL}{decline_path}"

    subject_prefix = "REMINDER: " if is_reminder else ""
    subject = f"{subject_prefix}Session Confirmation Required: {session_obj.school_group.name if session_obj.school_group else 'Session'} on {session_obj.session_date.strftime('%a, %d %b %Y')}"
    
    context = {
        'coach_name': coach_user.first_name or coach_user.username,
        'session_date': session_obj.session_date.strftime('%A, %d %B %Y'),
        'session_time': session_obj.session_start_time.strftime('%H:%M'),
        'session_group': session_obj.school_group.name if session_obj.school_group else "N/A",
        'session_venue': session_obj.venue_name or "N/A",
        'confirm_url': confirm_url,
        'decline_url': decline_url,
        'is_reminder': is_reminder,
        'site_name': "SquashSync" 
    }

    html_message = render_to_string('planning/emails/session_confirmation_email.html', context)
    plain_message = strip_tags(html_message)
    from_email = settings.DEFAULT_FROM_EMAIL

    try:
        send_mail(subject, plain_message, from_email, [coach_user.email], html_message=html_message)
        print(f"Sent session confirmation email to {coach_user.email} for session {session_obj.id}. Reminder: {is_reminder}")
        return True
    except Exception as e:
        print(f"Error sending session confirmation email to {coach_user.email}: {e}")
        return False

def verify_confirmation_token(token):
    """
    Verifies a signed token (now expecting a timestamp) and returns the payload.
    Returns None if the token is invalid or expired.
    """
    try:
        # max_age is now correctly handled by TimestampSigner's unsign method
        payload = confirmation_signer.unsign(token, max_age=timedelta(days=7)) 
        return payload
    except (BadSignature, SignatureExpired): # Catch both BadSignature and SignatureExpired
        print(f"Token verification failed: Invalid, tampered, or expired token.") # More specific log
        return None
    except Exception as e: 
        print(f"An unexpected error occurred during token verification: {e}")
        return None
