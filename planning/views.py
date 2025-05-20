# planning/views.py

import json
# Corrected datetime imports:
# Import the datetime class as dt_class to avoid conflict with the module name.
# Also import other necessary components like timedelta, date, and time.
from datetime import datetime as dt_class, timedelta, date, time
from collections import defaultdict # Keep if used elsewhere
import calendar # Keep if used elsewhere

from django.conf import settings # Keep if used elsewhere
from django.contrib import messages
from django.contrib.auth import get_user_model # Keep if used elsewhere
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import FieldError, ObjectDoesNotExist # Keep if used elsewhere
from django.db.models import Q, Prefetch, Count # Keep for general Django ORM use
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, Http404 # Consolidate HttpResponse types
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST # Keep if used elsewhere
from .utils import get_weekly_session_data 
import csv # <

# Your comprehensive model imports (this is good)
from .models import (
    Session, SchoolGroup, Player, Coach, Drill, TimeBlock,
    ActivityAssignment, SessionAssessment, CourtSprintRecord,
    VolleyRecord, BackwallDriveRecord, MatchResult,
    ManualCourtAssignment, CoachFeedback, CoachAvailability,
    CoachSessionCompletion
    # Ensure all models needed by any view in this file are listed
)

# Your SoloSync imports (conditional import is good)
try:
    from solosync_api.models import SoloSessionLog, SoloRoutine
    solosync_imported = True
except ImportError:
    print("Warning: Could not import SoloSync models. SoloSync features will be disabled.")
    SoloSessionLog = None
    SoloRoutine = None
    solosync_imported = False

# Your form imports (keep as is)
from .forms import (
    AttendanceForm, ActivityAssignmentForm, SessionAssessmentForm,
    CoachFeedbackForm, CourtSprintRecordForm, VolleyRecordForm,
    BackwallDriveRecordForm, MatchResultForm
    # Add other forms if you have them
)
Model = get_user_model()


def is_superuser(user):
    return user.is_authenticated and user.is_superuser

def is_coach(user):
    return user.is_authenticated and user.is_staff



# --- Coach Completion Report View (UPDATED with Date Filtering) ---
@login_required
@user_passes_test(is_superuser, login_url='login') # Assuming 'login' is your login URL name
def coach_completion_report_view(request):
    """
    Displays coach completion status for sessions within a selected month
    and allows superuser override of payment confirmation.
    Defaults to the previous month.
    """
    today = timezone.now().date()

    # --- Handle POST request for overriding payment confirmation ---
    if request.method == 'POST':
        completion_id = request.POST.get('completion_id')
        action = request.POST.get('action')
        
        # Get the month/year that was being viewed, to redirect back correctly
        # These should be submitted as hidden fields in the form that triggers the POST
        redirect_month_str = request.POST.get('filter_month')
        redirect_year_str = request.POST.get('filter_year')

        redirect_url = reverse('planning:coach_completion_report') # Use your actual URL name
        
        query_params = {}
        if redirect_month_str and redirect_year_str:
            try:
                query_params['month'] = int(redirect_month_str)
                query_params['year'] = int(redirect_year_str)
                redirect_url += f'?month={query_params["month"]}&year={query_params["year"]}'
            except ValueError:
                messages.warning(request, "Could not preserve filter due to invalid month/year in POST. Reverting to default.")


        if not completion_id or not action:
            messages.error(request, "Invalid request. Missing required data.")
            return redirect(redirect_url)

        try:
            completion_record = get_object_or_404(CoachSessionCompletion, pk=int(completion_id))

            if action == 'confirm':
                completion_record.confirmed_for_payment = True
                messages.success(request, f"Payment confirmed for {completion_record.coach.name} for session on {completion_record.session.session_date.strftime('%d %b %Y')}.")
            elif action == 'unconfirm':
                completion_record.confirmed_for_payment = False
                messages.warning(request, f"Payment confirmation removed for {completion_record.coach.name} for session on {completion_record.session.session_date.strftime('%d %b %Y')}.")
            else:
                messages.error(request, "Invalid action specified.")
                return redirect(redirect_url)
            
            completion_record.save(update_fields=['confirmed_for_payment'])

        except ValueError: messages.error(request, "Invalid ID format.")
        # Make sure CoachSessionCompletion is defined or imported for this exception
        except CoachSessionCompletion.DoesNotExist: messages.error(request, "Completion record not found.")
        except Exception as e: messages.error(request, f"An error occurred: {e}"); print(f"Error in coach_completion_report_view POST: {e}")
        
        return redirect(redirect_url)


    # --- Handle GET request ---

    # --- Date selection logic ---
    # Calculate default: previous month
    first_day_of_current_month = today.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    default_target_year = last_day_of_previous_month.year
    default_target_month = last_day_of_previous_month.month

    # Try to get year and month from GET parameters, otherwise use defaults
    try:
        target_year = int(request.GET.get('year', default_target_year))
        target_month = int(request.GET.get('month', default_target_month))
    except ValueError:
        messages.warning(request, "Invalid month/year parameters. Displaying report for the default period (previous month).")
        target_year = default_target_year
        target_month = default_target_month

    # --- Prepare choices for dropdowns ---
    # For year dropdown (e.g., current year and last 2 years)
    year_choices = [today.year - i for i in range(3)] # e.g., [2025, 2024, 2023]
    # Ensure the target_year (even if from GET param) is in choices, or default logic makes sense
    if target_year not in year_choices and target_year < today.year : # Add older years if selected
        year_choices.append(target_year)
        year_choices.sort(reverse=True)
    elif target_year > today.year : # If future year selected, revert to default
        messages.warning(request, "Future year selected, reverting to default period.")
        target_year = default_target_year
        target_month = default_target_month


    # For month dropdown
    month_name_choices = [{'value': i, 'name': calendar.month_name[i]} for i in range(1, 13)]

    # Validate that the selected month/year are plausible, if not, reset and warn.
    # (Basic validation, could be expanded if year_choices is dynamic based on data)
    if not (1 <= target_month <= 12):
        messages.warning(request, f"Invalid month ({target_month}) selected. Reverting to default period.")
        target_year = default_target_year
        target_month = default_target_month


    # Your existing 'available_months' for a combined "Month YYYY" dropdown
    # This generates a list like ["May 2025", "April 2025", ...]
    available_months_combined = []
    current_loop_date = today.replace(day=1) # Start from 1st of current month for consistency
    for _ in range(12): # Last 12 months including current
        available_months_combined.append({
            'year': current_loop_date.year, 
            'month': current_loop_date.month, 
            'name': current_loop_date.strftime('%B %Y')
        })
        # Move to the first of the previous month
        current_loop_date = (current_loop_date - timedelta(days=1)).replace(day=1)
    

    # --- Data fetching logic (remains the same) ---
    _, num_days = calendar.monthrange(target_year, target_month)
    start_date = date(target_year, target_month, 1)
    end_date = date(target_year, target_month, num_days)

    completion_records = CoachSessionCompletion.objects.filter(
        session__session_date__gte=start_date,
        session__session_date__lte=end_date
    ).select_related(
        'coach', 
        'coach__user',
        'session',
        'session__school_group'
    ).order_by(
        'session__session_date',
        'session__session_start_time',
        'coach__name'
    )
    
    context = {
        'completion_records': completion_records,
        'selected_year': target_year,
        'selected_month': target_month,
        'year_choices': year_choices, # For separate year dropdown
        'month_name_choices': month_name_choices, # For separate month dropdown
        'available_months_combined': available_months_combined, # For combined "Month YYYY" dropdown
        'start_date': start_date,
        'end_date': end_date,
        'page_title': f"Coach Completion Report ({start_date.strftime('%B %Y')})"
    }
    return render(request, 'planning/coach_completion_report.html', context)


# --- Session Staffing View (for Maryna/Superuser) ---
@login_required
@user_passes_test(is_superuser, login_url='login') # Only superusers
def session_staffing_view(request):
    """
    Allows a superuser (Maryna) to view upcoming sessions,
    see coach availability, and assign coaches to sessions.
    """
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        assigned_coach_ids = request.POST.getlist(f'coaches_for_session_{session_id}')

        if not session_id:
            messages.error(request, "Invalid request: Missing session ID.")
            return redirect('planning:session_staffing')

        try:
            session_to_update = get_object_or_404(Session, pk=int(session_id))
            selected_coaches = []
            if assigned_coach_ids:
                valid_coach_ids = [int(cid) for cid in assigned_coach_ids if cid.isdigit()]
                selected_coaches = Coach.objects.filter(pk__in=valid_coach_ids)
            session_to_update.coaches_attending.set(selected_coaches)
            messages.success(request, f"Coach assignments updated for session on {session_to_update.session_date.strftime('%d %b %Y')}.")
        except ValueError: messages.error(request, "Invalid session ID format.")
        except Session.DoesNotExist: messages.error(request, "Session not found.")
        except Exception as e: messages.error(request, f"An error occurred: {e}"); print(f"Error in session_staffing_view POST: {e}")

        return redirect('planning:session_staffing')

    # --- Handle GET request ---
    now = timezone.now()
    upcoming_sessions_qs = Session.objects.filter(
        session_date__gte=now.date(),
        session_date__lte=now.date() + timedelta(weeks=8)
    ).select_related('school_group').prefetch_related(
        'coaches_attending', # Prefetch Coach instances
        Prefetch( # Prefetch availability including the related User (coach)
            'coach_availabilities',
            queryset=CoachAvailability.objects.select_related('coach') # Fetch related User
        )
    ).order_by('session_date', 'session_start_time')

    # Prepare data for the template
    sessions_for_staffing = []
    all_coaches = Coach.objects.filter(is_active=True).select_related('user').order_by('name') # Select related user

    for session_obj in upcoming_sessions_qs:
        # Create a map of availability notes keyed by the User ID
        availability_notes_map = {
            ca.coach_id: ca.notes
            for ca in session_obj.coach_availabilities.all() if ca.coach_id is not None
        }
        # Create a set of User IDs who are available
        available_coach_user_ids = {
            ca.coach_id for ca in session_obj.coach_availabilities.all() if ca.is_available and ca.coach_id is not None
        }

        # Get Coach profiles corresponding to available users
        available_coach_profiles = []
        if available_coach_user_ids:
             # Fetch Coach objects whose 'user' field is in the available set
             available_coach_profiles = list(Coach.objects.filter(user_id__in=available_coach_user_ids, is_active=True))
             # Attach the notes to the coach profile object
             for coach_prof in available_coach_profiles:
                 coach_prof.availability_note = availability_notes_map.get(coach_prof.user_id, "")


        sessions_for_staffing.append({
            'session_obj': session_obj,
            'currently_assigned_coaches': list(session_obj.coaches_attending.all()),
            'available_coach_profiles': available_coach_profiles, # List of Coach objects with notes attached
            # 'availability_notes': availability_notes_map, # No longer needed directly in template
        })

    context = {
        'sessions_for_staffing': sessions_for_staffing,
        'all_coaches': all_coaches,
        'page_title': "Session Staffing & Coach Availability"
    }
    return render(request, 'planning/session_staffing.html', context)

    # --- Handle GET request ---
    now = timezone.now()
    # Get upcoming sessions (e.g., next 8 weeks for staffing view)
    upcoming_sessions_qs = Session.objects.filter(
        session_date__gte=now.date(),
        session_date__lte=now.date() + timedelta(weeks=8)
    ).select_related('school_group').prefetch_related(
        'coaches_attending', # Prefetch currently assigned coaches (Coach model instances)
        'coach_availabilities__coach' # Prefetch User instances from CoachAvailability
    ).order_by('session_date', 'session_start_time')

    # Prepare data for the template
    sessions_for_staffing = []
    all_coaches = Coach.objects.filter(is_active=True).order_by('name') # Get all active custom Coach instances

    for session_obj in upcoming_sessions_qs:
        # Get User instances who marked themselves available
        available_coach_users = User.objects.filter(
            session_availabilities__session=session_obj,
            session_availabilities__is_available=True,
            is_staff=True # Ensure they are staff
        ).distinct()

        # Map available User instances to Coach instances (if your Coach model has a 'user' link)
        # This list will contain Coach model instances that are available
        available_coach_profiles = []
        for user_obj in available_coach_users:
            try:
                # Assumes Coach model has a OneToOneField to User named 'user'
                # or User has a OneToOneField to Coach named 'coach_profile'
                if hasattr(user_obj, 'coach_profile') and user_obj.coach_profile:
                    available_coach_profiles.append(user_obj.coach_profile)
                else: # Fallback: Try to find Coach by matching User to Coach.user field
                    coach_prof = Coach.objects.filter(user=user_obj).first()
                    if coach_prof:
                        available_coach_profiles.append(coach_prof)
            except ObjectDoesNotExist: # Or User.coach_profile.RelatedObjectDoesNotExist
                pass # Coach profile might not exist for every staff user

        # Get notes from available coaches
        availability_notes = {}
        for ca in session_obj.coach_availabilities.filter(is_available=True):
            if ca.coach: # coach is a User instance here
                availability_notes[ca.coach.id] = ca.notes


        sessions_for_staffing.append({
            'session_obj': session_obj,
            'currently_assigned_coaches': list(session_obj.coaches_attending.all()), # List of Coach instances
            'available_coach_users': list(available_coach_users), # List of User instances
            'available_coach_profiles': list(set(available_coach_profiles)), # Unique Coach instances
            'availability_notes': availability_notes, # Dict: {user_id: notes}
        })

    context = {
        'sessions_for_staffing': sessions_for_staffing,
        'all_coaches': all_coaches, # For the form select options (Coach instances)
        'page_title': "Session Staffing & Coach Availability"
    }
    return render(request, 'planning/session_staffing.html', context)

@login_required
@user_passes_test(is_coach, login_url='login')
def my_availability_view(request):
    """
    Allows a logged-in coach (staff user) to view upcoming sessions
    and mark their availability for each. Notifies superusers on cancellation.
    """
    current_coach_profile = None
    try:
        # This assumes Coach model has a 'user' field linking to the User model
        current_coach_profile = Coach.objects.filter(user=request.user).first()
        # Or if User model has 'coach_profile' related name:
        # current_coach_profile = request.user.coach_profile
        if not current_coach_profile:
             # If no Coach profile exists for this staff User, they can't be assigned anyway
             # but they can still set availability using their User account.
             # Depending on requirements, you might want to prevent this.
             print(f"Warning: No Coach profile found linked to User {request.user.username}")

    except AttributeError: # Handles if User model doesn't have coach_profile
         print(f"AttributeError finding coach profile for user {request.user.username}")
    except Coach.DoesNotExist: # Handles if Coach model query fails (less likely with filter().first())
         print(f"Coach.DoesNotExist finding profile for user {request.user.username}")
    # Allow view to proceed even if coach profile isn't found, they just can't be assigned/unassigned

    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        availability_status_str = request.POST.get('is_available')
        notes_from_form = request.POST.get('notes', '')

        if not session_id or availability_status_str is None:
            messages.error(request, "Invalid request. Missing session or availability status.")
            return redirect('planning:my_availability')

        try:
            session_to_update = get_object_or_404(Session, pk=int(session_id))
            is_available_bool = availability_status_str.lower() == 'true'

            # Get or create the availability record for the logged-in User
            availability_record, created = CoachAvailability.objects.update_or_create(
                coach=request.user, # Links to the User model instance
                session=session_to_update,
                defaults={'is_available': is_available_bool, 'notes': notes_from_form}
            )

            if created:
                messages.success(request, f"Availability set for session on {session_to_update.session_date.strftime('%d %b %Y')}.")
            else:
                messages.success(request, f"Availability updated for session on {session_to_update.session_date.strftime('%d %b %Y')}.")

            # If a coach marks themselves as unavailable for a session they were assigned to
            if not is_available_bool and current_coach_profile: # Check if coach_profile was found
                if current_coach_profile in session_to_update.coaches_attending.all():
                    session_to_update.coaches_attending.remove(current_coach_profile)
                    removed_coach_name = current_coach_profile.name # Get name for message
                    messages.info(request, f"You have been removed from the assigned coaches for session on {session_to_update.session_date.strftime('%d %b %Y')}.")

                    # *** ADD NOTIFICATION FOR SUPERUSERS ***
                    superuser_message = f"Coach {removed_coach_name} is now unavailable for session: {session_to_update} on {session_to_update.session_date.strftime('%d %b')}. Please check staffing."
                    # Send message to all superusers (using Django messages framework)
                    # Note: This message will appear for *any* superuser loading *any* page next.
                    # A more targeted notification system would be better long-term.
                    admin_users = UserModel.objects.filter(is_superuser=True, is_active=True)
                    for admin_user in admin_users:
                         # We can't directly add a message for another user's request here.
                         # This requires a proper notification model or external system.
                         # For now, we can only log it server-side or show a message
                         # to the current user indicating admins *should* be notified.
                         print(f"NOTIFICATION NEEDED for Superusers: {superuser_message}") # Log for now
                    messages.warning(request, "Admin has been notified of your unavailability for this assigned session.") # Inform the coach

        except ValueError:
            messages.error(request, "Invalid session ID.")
        except Session.DoesNotExist:
            messages.error(request, "Session not found.")
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            print(f"Error in my_availability_view POST: {e}")

        return redirect('planning:my_availability')

    # --- Handle GET request ---
    now = timezone.now()
    upcoming_sessions_qs = Session.objects.filter(
        session_date__gte=now.date(),
        session_date__lte=now.date() + timedelta(weeks=4)
    ).select_related('school_group').prefetch_related('coaches_attending').order_by('session_date', 'session_start_time')

    coach_availabilities = CoachAvailability.objects.filter(
        coach=request.user,
        session__in=upcoming_sessions_qs
    ).values('session_id', 'is_available', 'notes')

    availability_map = {
        item['session_id']: {'is_available': item['is_available'], 'notes': item['notes']}
        for item in coach_availabilities
    }

    sessions_with_availability = []
    for session_obj in upcoming_sessions_qs:
        availability_info = availability_map.get(session_obj.id)
        is_assigned_to_this_session = False
        if current_coach_profile: # Check if coach_profile was found earlier
            is_assigned_to_this_session = current_coach_profile in session_obj.coaches_attending.all()

        sessions_with_availability.append({
            'session_obj': session_obj,
            'is_available': availability_info['is_available'] if availability_info is not None else True,
            'notes': availability_info['notes'] if availability_info else "",
            'is_assigned': is_assigned_to_this_session
        })

    context = {
        'sessions_with_availability': sessions_with_availability,
        'page_title': "My Availability for Upcoming Sessions"
    }
    return render(request, 'planning/my_availability.html', context)

# === Helper Function for Live Session State Calculation ===
def _get_live_session_state(session, effective_time):
    ...

# === Views start here ===
@login_required
@user_passes_test(is_coach, login_url='login')
def live_session_view(request, session_id):
    session = get_object_or_404(Session.objects.select_related('school_group'), pk=session_id)
    now = timezone.now()
    sim_time_str = request.GET.get('sim_time')
    is_simulated = False
    effective_time_aware = now
    sim_time_input_value = now.strftime('%Y-%m-%dT%H:%M')

    if sim_time_str:
        try:
            naive_sim_time = datetime.datetime.strptime(sim_time_str, '%Y-%m-%dT%H:%M')
            current_tz = timezone.get_current_timezone()
            effective_time_aware = timezone.make_aware(naive_sim_time, current_tz)
            is_simulated = True
            sim_time_input_value = sim_time_str
        except ValueError:
            messages.warning(request, "Invalid simulation time format provided.")

    try:
        effective_time_iso_formatted = effective_time_aware.isoformat(timespec='seconds')
    except TypeError:
        effective_time_iso_formatted = effective_time_aware.replace(microsecond=0).isoformat()

    context = {
        'session': session,
        'is_simulated': is_simulated,
        'effective_time_iso': effective_time_iso_formatted,
        'sim_time_input_value': sim_time_input_value,
        'page_title': f"Live Session: {session.school_group.name if session.school_group else ''} {session.session_date.strftime('%d %b')}"
    }
    return render(request, 'planning/live_session.html', context)

@login_required
@user_passes_test(is_coach, login_url='login')
@require_GET
def live_session_update_api(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    now = timezone.now()
    sim_time_iso_str = request.GET.get('sim_time_iso')
    effective_time = now

    if sim_time_iso_str:
        try:
            parsed_time = datetime.datetime.fromisoformat(sim_time_iso_str.replace('Z',''))
            if timezone.is_naive(parsed_time):
                current_tz = timezone.get_current_timezone()
                effective_time = timezone.make_aware(parsed_time, current_tz)
            else:
                effective_time = timezone.localtime(parsed_time)
        except ValueError:
            effective_time = now

    live_state_data = _get_live_session_state(session, effective_time)
    return JsonResponse(live_state_data)

# --- Homepage View (Added Superuser Context for Staffing) ---
# --- Homepage View (UPDATED Reminder Query) ---
@login_required
@user_passes_test(is_coach, login_url='login')
def homepage_view(request):
    """
    Displays the main homepage / dashboard for logged-in coaches.
    Filters upcoming sessions and feedback reminders based on coach assignment if not superuser.
    """
    now = timezone.now()
    user = request.user
    coach_profile = None # Initialize coach profile

    # Try to get the linked Coach profile for non-superusers
    if not user.is_superuser:
        try:
            coach_profile = user.coach_profile # Assumes related_name='coach_profile'
            # Or use: coach_profile = Coach.objects.get(user=user)
        except ObjectDoesNotExist:
            messages.warning(request, "Your user account is not linked to a Coach profile.")
        except AttributeError:
            messages.error(request, "Could not determine your coach profile.")

    # --- Upcoming Sessions (Filtered by Role) ---
    upcoming_sessions_base_qs = Session.objects.filter(
        Q(session_date__gt=now.date()) | Q(session_date=now.date(), session_start_time__gte=now.time())
    ).select_related('school_group')

    if user.is_superuser:
        upcoming_sessions = upcoming_sessions_base_qs.order_by('session_date', 'session_start_time')[:5]
    elif coach_profile: # Filter only if coach profile was found
        upcoming_sessions = upcoming_sessions_base_qs.filter(
            coaches_attending=coach_profile
        ).order_by('session_date', 'session_start_time')[:5]
    else: # Non-superuser without a coach profile sees no upcoming sessions
        upcoming_sessions = Session.objects.none()


    # --- Recently Finished Sessions for Feedback Reminder (Filtered by Role) ---
    feedback_window_start = now - timedelta(days=14)
    fifteen_days_ago = now.date() - timedelta(days=15)

    potential_sessions_base_qs = Session.objects.filter(
        session_date__gte=fifteen_days_ago,
        session_date__lte=now.date(),
        assessments_complete=False
    ).select_related('school_group').prefetch_related('coaches_attending') # Prefetch coaches

    # Filter further for regular coaches
    if user.is_superuser:
        potential_sessions = potential_sessions_base_qs.order_by('-session_date', '-session_start_time')
    elif coach_profile:
        # Filter for sessions this specific coach was assigned to
        potential_sessions = potential_sessions_base_qs.filter(
            coaches_attending=coach_profile
        ).order_by('-session_date', '-session_start_time')
    else: # Non-superuser without coach profile sees no reminders
        potential_sessions = Session.objects.none()

    # Now loop through the potentially filtered list
    recent_sessions_for_feedback = []
    for session in potential_sessions: # This queryset is already filtered by role
        if session.end_datetime:
            end_dt_aware = session.end_datetime
            is_in_window = False
            if timezone.is_aware(end_dt_aware) and timezone.is_aware(feedback_window_start) and timezone.is_aware(now):
                 if feedback_window_start <= end_dt_aware < now: is_in_window = True
            elif not timezone.is_aware(end_dt_aware) and not timezone.is_aware(feedback_window_start) and not timezone.is_aware(now):
                 if feedback_window_start.replace(tzinfo=None) <= end_dt_aware < now.replace(tzinfo=None): is_in_window = True

            if is_in_window:
                recent_sessions_for_feedback.append(session)
        if len(recent_sessions_for_feedback) >= 5: break


    # --- Fetch Recent SoloSync Logs ---
    recent_solo_logs = []
    if solosync_imported and SoloSessionLog is not None:
        try:
            recent_solo_logs = SoloSessionLog.objects.select_related(
                'player', 'routine'
            ).order_by('-completion_date')[:10]
        except FieldError as e: print(f"FieldError fetching SoloSessionLog: {e}")
        except Exception as e: print(f"Error fetching SoloSessionLog: {e}")

    # --- Context for Superuser (Maryna) ---
    unstaffed_session_count = 0
    if request.user.is_superuser:
        two_weeks_from_now = now.date() + timedelta(weeks=2)
        unstaffed_sessions = Session.objects.filter(
            session_date__gte=now.date(),
            session_date__lte=two_weeks_from_now,
            coaches_attending__isnull=True
        ).distinct()
        unstaffed_session_count = unstaffed_sessions.count()

    context = {
        'upcoming_sessions': upcoming_sessions, # Now potentially filtered
        'recent_sessions_for_feedback': recent_sessions_for_feedback, # Now potentially filtered
        'recent_solo_logs': recent_solo_logs,
        'unstaffed_session_count': unstaffed_session_count,
        'page_title': "Coach Dashboard"
    }
    return render(request, 'planning/homepage.html', context)

@login_required
@user_passes_test(is_coach, login_url='login')
def add_activity(request, block_id, court_num):
    time_block = get_object_or_404(TimeBlock.objects.select_related('session'), pk=block_id)
    session = time_block.session
    if request.method == 'POST':
        form = ActivityAssignmentForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.time_block = time_block
            activity.court_number = court_num
            last_activity = ActivityAssignment.objects.filter(
                time_block=time_block, court_number=court_num
            ).order_by('-order').first()
            activity.order = (last_activity.order + 1) if last_activity else 0
            activity.save()
            messages.success(request, f"Activity '{activity}' added successfully.")
            return redirect('planning:session_detail', session_id=session.id)
    else:
        form = ActivityAssignmentForm(initial={'duration_minutes': 15})

    context = {
        'form': form,
        'time_block': time_block,
        'session': session,
        'court_num': court_num,
        'page_title': 'Add Activity'
    }
    return render(request, 'planning/add_activity_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def edit_activity(request, activity_id):
    activity_instance = get_object_or_404(ActivityAssignment.objects.select_related('time_block__session'), pk=activity_id)
    session = activity_instance.time_block.session
    if request.method == 'POST':
        form = ActivityAssignmentForm(request.POST, instance=activity_instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Activity updated successfully.")
            return redirect('planning:session_detail', session_id=session.id)
    else:
        form = ActivityAssignmentForm(instance=activity_instance)

    context = {
        'form': form,
        'activity_instance': activity_instance,
        'time_block': activity_instance.time_block,
        'session': session,
        'court_num': activity_instance.court_number,
        'page_title': 'Edit Activity'
    }
    return render(request, 'planning/add_activity_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
@require_POST
def delete_activity(request, activity_id):
    activity_instance = get_object_or_404(ActivityAssignment, pk=activity_id)
    session_id = activity_instance.time_block.session_id
    activity_name = str(activity_instance)
    activity_instance.delete()
    messages.success(request, f"Activity '{activity_name}' deleted successfully.")
    return redirect('planning:session_detail', session_id=session_id)

@login_required
@user_passes_test(is_coach, login_url='login')
def player_profile(request, player_id):
    player = get_object_or_404(Player.objects.prefetch_related('school_groups'), pk=player_id)
    
    # Session Attendance Logic (remains the same)
    sessions_attended_qs = player.attended_sessions.filter(session_date__lte=timezone.now().date()).order_by('-session_date', '-session_start_time')
    attended_sessions_count = sessions_attended_qs.count()
    player_group_ids = player.school_groups.values_list('id', flat=True)
    total_relevant_sessions_count = 0
    attendance_percentage = None
    if player_group_ids:
        total_relevant_sessions_count = Session.objects.filter(
            school_group_id__in=player_group_ids, 
            session_date__lte=timezone.now().date()
        ).count()
        if total_relevant_sessions_count > 0:
            attendance_percentage = round((attended_sessions_count / total_relevant_sessions_count) * 100)
        elif attended_sessions_count == 0:
            attendance_percentage = None # Explicitly None if no relevant sessions

    # --- MODIFIED Assessment Fetching Logic ---
    assessments_base_qs = player.session_assessments.select_related(
        'session', 
        'session__school_group', 
        'submitted_by' # Prefetch the user who submitted the assessment
    ).order_by('-date_recorded', '-session__session_start_time')

    if request.user.is_superuser:
        # Superusers see all assessments, including hidden ones
        assessments = assessments_base_qs.all()
    elif request.user.is_staff: # For regular coaches (staff but not superuser)
        # Regular coaches only see non-hidden assessments
        assessments = assessments_base_qs.filter(is_hidden=False)
    else:
        # This case should ideally not be reached due to @user_passes_test(is_coach)
        # If it were, non-staff users would see no assessments.
        assessments = player.session_assessments.none()
    # --- END MODIFIED Assessment Fetching Logic ---

    # Metric Records & Chart Data Preparation (remains the same)
    sprints = player.sprint_records.select_related('session').order_by('date_recorded')
    volleys = player.volley_records.select_related('session').order_by('date_recorded')
    drives = player.drive_records.select_related('session').order_by('date_recorded')
    matches = player.match_results.select_related('session').order_by('-date')

    sprint_chart_data = defaultdict(lambda: {'labels': [], 'data': []})
    for sprint in sprints:
        key = sprint.duration_choice # Assuming this is how you categorize sprint types
        sprint_chart_data[key]['labels'].append(sprint.date_recorded.isoformat())
        sprint_chart_data[key]['data'].append(sprint.score)

    volley_chart_data = defaultdict(lambda: {'labels': [], 'data': []})
    for volley in volleys:
        key = volley.shot_type
        volley_chart_data[key]['labels'].append(volley.date_recorded.isoformat())
        volley_chart_data[key]['data'].append(volley.consecutive_count)

    drive_chart_data = defaultdict(lambda: {'labels': [], 'data': []})
    for drive in drives:
        key = drive.shot_type
        drive_chart_data[key]['labels'].append(drive.date_recorded.isoformat())
        drive_chart_data[key]['data'].append(drive.consecutive_count)

    context = {
        'player': player,
        'sessions_attended': sessions_attended_qs,
        'attended_sessions_count': attended_sessions_count,
        'total_relevant_sessions_count': total_relevant_sessions_count,
        'attendance_percentage': attendance_percentage,
        'assessments': assessments, # Pass the filtered assessments
        'sprints': sprints,
        'volleys': volleys,
        'drives': drives,
        'matches': matches,
        'sprint_chart_data': dict(sprint_chart_data),
        'volley_chart_data': dict(volley_chart_data),
        'drive_chart_data': dict(drive_chart_data),
        # 'user' is automatically available in templates if using RequestContext
    }
    return render(request, 'planning/player_profile.html', context)



# --- Assessment Views (UPDATED to auto-confirm payment) ---
@login_required
@user_passes_test(is_coach, login_url='login')
def assess_player_session(request, session_id, player_id):
    """ Handles ADDING a new assessment & marks completion/payment """
    session = get_object_or_404(Session, pk=session_id)
    player = get_object_or_404(Player, pk=player_id)
    assessment_instance = SessionAssessment.objects.filter(session=session, player=player).first()

    if assessment_instance: # If already exists, redirect to edit
         return redirect('planning:edit_session_assessment', assessment_id=assessment_instance.id)

    if request.method == 'POST':
        form = SessionAssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.session = session
            assessment.player = player
            assessment.submitted_by = request.user # Assign logged-in user
            if not form.cleaned_data.get('date_recorded'):
                 assessment.date_recorded = session.session_date
            assessment.save()
            messages.success(request, f"Assessment added for {player.full_name} in session on {session.session_date.strftime('%d %b')}.")

            # *** Mark coach completion AND confirm payment ***
            try:
                coach_profile = Coach.objects.filter(user=request.user).first()
                if coach_profile:
                    completion, created = CoachSessionCompletion.objects.update_or_create(
                        coach=coach_profile,
                        session=session,
                        # Set both flags to True when an assessment is submitted
                        defaults={'assessments_submitted': True, 'confirmed_for_payment': True}
                    )
                    print(f"Marked completion/payment for {coach_profile.name} for session {session.id}")
            except ObjectDoesNotExist: print(f"Could not find Coach profile for user {request.user.username} to mark completion.")
            except AttributeError: print(f"AttributeError finding Coach profile for user {request.user.username} to mark completion.")
            except Exception as e: print(f"Error updating CoachSessionCompletion: {e}")
            # *** End mark coach completion ***

            return redirect('planning:pending_assessments')
    else:
        form = SessionAssessmentForm()

    context = {
        'form': form, 'session': session, 'player': player,
        'assessment_instance': None, 'page_title': f"Add Assessment for {player.full_name}"
    }
    return render(request, 'planning/assess_player_form.html', context)

@login_required
@user_passes_test(is_coach, login_url='login')
def edit_session_assessment(request, assessment_id):
    """ Handles EDITING an existing assessment & ensures completion/payment marked """
    assessment_instance = get_object_or_404(SessionAssessment.objects.select_related('player', 'session', 'submitted_by'), pk=assessment_id)
    player = assessment_instance.player
    session = assessment_instance.session
    original_submitter = assessment_instance.submitted_by 

    # --- PERMISSION CHECK ---
    if not (request.user.is_superuser or original_submitter == request.user):
        messages.error(request, "You do not have permission to edit this assessment.")
        return redirect('planning:player_profile', player_id=player.id)
    # --- END PERMISSION CHECK ---

    # Assuming SessionAssessmentForm is defined in your forms.py
    from .forms import SessionAssessmentForm # Import locally or ensure it's at the top

    if request.method == 'POST':
        form = SessionAssessmentForm(request.POST, instance=assessment_instance)
        if form.is_valid():
            assessment = form.save(commit=False)
            # Ensure submitted_by isn't changed on edit if it's part of the form
            # (though it's better if submitted_by is not an editable field in SessionAssessmentForm)
            assessment.submitted_by = original_submitter 
            assessment.save()
            messages.success(request, f"Assessment for {player.full_name} (Session: {session.session_date.strftime('%d %b')}) updated.")

            # Mark coach completion AND confirm payment (use original submitter)
            if original_submitter: 
                try:
                    # Find Coach profile linked to the *original submitter*
                    coach_profile = Coach.objects.filter(user=original_submitter).first()
                    if coach_profile:
                        completion, created = CoachSessionCompletion.objects.update_or_create(
                            coach=coach_profile,
                            session=session,
                            defaults={'assessments_submitted': True, 'confirmed_for_payment': True}
                        )
                        print(f"Marked completion/payment (on edit) for {coach_profile.name} for session {session.id}")
                    else: # Added else for clarity
                        print(f"Could not find Coach profile for user {original_submitter.username} to mark completion (on edit).")
                except ObjectDoesNotExist: 
                    print(f"ObjectDoesNotExist: Could not find Coach profile for user {original_submitter.username} to mark completion.")
                except AttributeError: 
                    print(f"AttributeError finding Coach profile for user {original_submitter.username} to mark completion.")
                except Exception as e: 
                    print(f"Error updating CoachSessionCompletion on edit: {e}")
            
            return redirect('planning:player_profile', player_id=player.id)
    else:
        form = SessionAssessmentForm(instance=assessment_instance)

    context = {
        'form': form, 
        'session': session, 
        'player': player,
        'assessment_instance': assessment_instance, 
        'page_title': f'Edit Assessment for {player.full_name}'
    }
    return render(request, 'planning/assess_player_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
@require_POST # Good practice for delete actions
def delete_session_assessment(request, assessment_id):
    assessment_instance = get_object_or_404(SessionAssessment.objects.select_related('player', 'submitted_by'), pk=assessment_id)
    player = assessment_instance.player # Get player for redirect before deleting
    original_submitter = assessment_instance.submitted_by

    # --- PERMISSION CHECK ---
    if not (request.user.is_superuser or original_submitter == request.user):
        messages.error(request, "You do not have permission to delete this assessment.")
        return redirect('planning:player_profile', player_id=player.id)
    # --- END PERMISSION CHECK ---

    assessment_instance.delete()
    messages.success(request, "Session assessment deleted successfully.")
    return redirect('planning:player_profile', player_id=player.id)



@login_required
@user_passes_test(is_coach, login_url='login')
def assess_latest_session_redirect(request, player_id):
    # ... (keep existing logic) ...
    player = get_object_or_404(Player, pk=player_id)
    latest_session = player.attended_sessions.order_by('-session_date', '-session_start_time').first()
    if latest_session:
        assessment_instance = SessionAssessment.objects.filter(session=latest_session, player=player).first()
        if assessment_instance: return redirect('planning:edit_session_assessment', assessment_id=assessment_instance.id)
        else: return redirect('planning:assess_player_session', session_id=latest_session.id, player_id=player.id)
    else: messages.warning(request, f"{player.full_name} has no recorded session attendance to assess."); return redirect('planning:player_profile', player_id=player.id)


@login_required
@user_passes_test(is_coach, login_url='login')
def pending_assessments_view(request):
    if request.method == 'POST':
        session_ids_to_complete = request.POST.getlist('sessions_to_complete')
        if session_ids_to_complete:
            sessions_updated = Session.objects.filter(id__in=session_ids_to_complete, assessments_complete=False).update(assessments_complete=True)
            if sessions_updated > 0:
                messages.success(request, f"{sessions_updated} session(s) marked as assessment complete.")
            else:
                messages.info(request, "No sessions were updated (they might have already been marked complete).")
        else:
            messages.warning(request, "No sessions selected to mark as complete.")
        return redirect('planning:pending_assessments')

    two_weeks_ago = timezone.now().date() - timedelta(days=14)
    pending_sessions_qs = Session.objects.filter(
        session_date__gte=two_weeks_ago,
        assessments_complete=False
    ).select_related('school_group').prefetch_related(
        Prefetch('attendees', queryset=Player.objects.order_by('last_name', 'first_name'))
    ).order_by('-session_date', '-session_start_time')

    grouped_sessions = defaultdict(list)
    for session in pending_sessions_qs:
        grouped_sessions[session.session_date].append(session)

    context = {
        'grouped_pending_sessions': dict(grouped_sessions),
        'page_title': "Pending Assessments"
    }
    return render(request, 'planning/pending_assessments.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def add_coach_feedback(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    if request.method == 'POST':
        form = CoachFeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.player = player
            feedback.save()
            messages.success(request, f"Feedback added for {player.full_name}.")
            return redirect('planning:player_profile', player_id=player.id)
    else:
        form = CoachFeedbackForm()
    context = {
        'form': form,
        'player': player,
        'page_title': f'Add Feedback for {player.full_name}'
    }
    return render(request, 'planning/add_coach_feedback_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def edit_coach_feedback(request, feedback_id):
    feedback_instance = get_object_or_404(CoachFeedback, pk=feedback_id)
    player = feedback_instance.player
    if request.method == 'POST':
        form = CoachFeedbackForm(request.POST, instance=feedback_instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"Feedback for {player.full_name} updated.")
            return redirect('planning:player_profile', player_id=player.id)
    else:
        form = CoachFeedbackForm(instance=feedback_instance)
    context = {
        'form': form,
        'player': player,
        'feedback_instance': feedback_instance,
        'page_title': f'Edit Feedback for {player.full_name}'
    }
    return render(request, 'planning/add_coach_feedback_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
@require_POST
def delete_coach_feedback(request, feedback_id):
    feedback_instance = get_object_or_404(CoachFeedback, pk=feedback_id)
    player = feedback_instance.player
    feedback_instance.delete()
    messages.success(request, "Feedback entry deleted successfully.")
    return redirect('planning:player_profile', player_id=player.id)

@login_required
@user_passes_test(is_coach, login_url='login')
@require_POST
def update_manual_assignment_api(request):
    try:
        data = json.loads(request.body)
        player_id = data.get('player_id')
        time_block_id = data.get('time_block_id')
        court_number_str = data.get('court_number')

        if court_number_str is None:
            raise ValueError("Missing court_number")
        court_number = int(court_number_str)

    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'status': 'error', 'message': f'Invalid data: {e}'}, status=400)

    if not all([player_id, time_block_id]):
        return JsonResponse({'status': 'error', 'message': 'Missing player_id or time_block_id'}, status=400)

    try:
        player = Player.objects.get(pk=player_id)
        time_block = TimeBlock.objects.get(pk=time_block_id)
    except ObjectDoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Player or TimeBlock not found'}, status=404)

    if court_number > time_block.number_of_courts or court_number < 1:
        return JsonResponse({'status': 'error', 'message': 'Invalid court number for this block'}, status=400)

    try:
        assignment, created = ManualCourtAssignment.objects.update_or_create(
            time_block=time_block,
            player=player,
            defaults={'court_number': court_number}
        )
        return JsonResponse({'status': 'success', 'message': 'Assignment updated'})
    except Exception as e:
        print(f"Error saving manual assignment: {e}")
        return JsonResponse({'status': 'error', 'message': 'Could not save assignment.'}, status=500)


@login_required
@user_passes_test(is_coach, login_url='login')
@require_POST
def clear_manual_assignments_api(request, time_block_id):
    deleted_count, _ = ManualCourtAssignment.objects.filter(time_block_id=time_block_id).delete()
    return JsonResponse({'status': 'success', 'message': f'{deleted_count} manual assignments cleared.'})


@login_required
@user_passes_test(is_coach, login_url='login')
def solosync_log_list_view(request):
    """ Displays a list of all submitted SoloSync session logs. """
    log_list = []
    if solosync_imported and SoloSessionLog is not None:
        log_list = SoloSessionLog.objects.select_related(
            'player', 'routine'
        ).order_by('-completed_at')
    else:
        messages.warning(request, "SoloSync models not available.")

    context = {
        'solo_session_logs': log_list,
        'page_title': "SoloSync Session Logs"
    }
    return render(request, 'planning/solosync_log_list.html', context)

@login_required
@user_passes_test(is_coach, login_url='login')
def add_sprint_record(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    if request.method == 'POST':
        form = CourtSprintRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.player = player
            record.save()
            messages.success(request, "Sprint record saved.")
            return redirect('planning:player_profile', player_id=player.id)
    else:
        form = CourtSprintRecordForm()
    context = {
        'form': form,
        'player': player,
        'page_title': 'Add Sprint Record'
    }
    return render(request, 'planning/add_sprint_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def add_volley_record(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    if request.method == 'POST':
        form = VolleyRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.player = player
            record.save()
            messages.success(request, "Volley record saved.")
            return redirect('planning:player_profile', player_id=player.id)
    else:
        form = VolleyRecordForm()
    context = {
        'form': form,
        'player': player,
        'page_title': 'Add Volley Record'
    }
    return render(request, 'planning/add_volley_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def add_drive_record(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    if request.method == 'POST':
        form = BackwallDriveRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.player = player
            record.save()
            messages.success(request, "Drive record saved.")
            return redirect('planning:player_profile', player_id=player.id)
    else:
        form = BackwallDriveRecordForm()
    context = {
        'form': form,
        'player': player,
        'page_title': 'Add Drive Record'
    }
    return render(request, 'planning/add_drive_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def add_match_result(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    if request.method == 'POST':
        form = MatchResultForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.player = player
            record.save()
            messages.success(request, "Match result saved.")
            return redirect('planning:player_profile', player_id=player.id)
    else:
        form = MatchResultForm()
    context = {
        'form': form,
        'player': player,
        'page_title': 'Add Match Result'
    }
    return render(request, 'planning/add_match_form.html', context)


# --- Session List View (UPDATED FOR ROLES) ---
@login_required
@user_passes_test(is_coach, login_url='login') # Ensure only coaches access this list
def session_list(request):
    """ Displays sessions: all for superuser, assigned only for regular coach. """
    user = request.user
    sessions_queryset = Session.objects.select_related('school_group').prefetch_related('coaches_attending')

    if user.is_superuser:
        # Superuser sees all sessions
        sessions_list = sessions_queryset.order_by('-session_date', '-session_start_time')
        page_title = 'All Sessions'
    else:
        # Regular coach sees only sessions they are assigned to
        try:
            # Find the Coach profile linked to this user
            coach_profile = user.coach_profile # Assumes related_name='coach_profile' on User model
            # Or use: coach_profile = Coach.objects.get(user=user) # If Coach.user exists
            sessions_list = sessions_queryset.filter(
                coaches_attending=coach_profile
            ).order_by('-session_date', '-session_start_time')
            page_title = 'My Assigned Sessions'
        except ObjectDoesNotExist: # Or User.coach_profile.RelatedObjectDoesNotExist:
             messages.warning(request, "Your user account is not linked to a Coach profile. Cannot show assigned sessions.")
             sessions_list = Session.objects.none() # Return empty queryset
             page_title = 'My Assigned Sessions'
        except AttributeError: # If coach_profile doesn't exist on user
             messages.error(request, "Could not determine your coach profile.")
             sessions_list = Session.objects.none()
             page_title = 'My Assigned Sessions'


    context = {
        'sessions_list': sessions_list,
        'page_title': page_title
    }
    return render(request, 'planning/session_list.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def session_detail(request, session_id):
    session = get_object_or_404(Session.objects.prefetch_related('time_blocks'), pk=session_id)
    time_blocks = session.time_blocks.all()
    current_attendees = session.attendees.all().order_by('last_name', 'first_name')
    school_group_for_session = session.school_group
    activities = ActivityAssignment.objects.filter(
        time_block__session=session
    ).select_related('drill', 'lead_coach').order_by(
        'time_block__start_offset_minutes', 'court_number', 'order'
    )

    initial_attendance = {'attendees': current_attendees}
    attendance_form = AttendanceForm(initial=initial_attendance, school_group=school_group_for_session)

    if request.method == 'POST' and 'update_attendance' in request.POST:
        attendance_form = AttendanceForm(request.POST, school_group=school_group_for_session)
        if attendance_form.is_valid():
            selected_players = attendance_form.cleaned_data['attendees']
            session.attendees.set(selected_players)
            ManualCourtAssignment.objects.filter(time_block__session=session).delete()
            messages.success(request, "Attendance updated.")
            return redirect('planning:session_detail', session_id=session.id)

    block_data = []
    display_attendees = session.attendees.all().order_by('last_name', 'first_name')
    if display_attendees.exists() and school_group_for_session:
        manual_assignments_all = ManualCourtAssignment.objects.filter(
            time_block__session=session, player__in=display_attendees
        ).select_related('player').values('time_block_id', 'player_id', 'court_number')

        manual_map = defaultdict(dict)
        for ma in manual_assignments_all:
            manual_map[ma['time_block_id']][ma['player_id']] = ma['court_number']

        for block in time_blocks:
            auto_assignments = _calculate_skill_priority_groups(display_attendees, block.number_of_courts)
            block_manuals = manual_map.get(block.id, {})
            manually_assigned_player_ids = set(block_manuals.keys())
            final_assignments = defaultdict(list)

            for court_num in range(1, block.number_of_courts + 1):
                final_assignments[court_num] = list(auto_assignments.get(court_num, []))

            for court_num in range(1, block.number_of_courts + 1):
                current_court_list = final_assignments[court_num]
                final_assignments[court_num] = [p for p in current_court_list if p.id not in manually_assigned_player_ids]

            for player_id, target_court in block_manuals.items():
                player_obj = next((p for p in display_attendees if p.id == player_id), None)
                if player_obj and player_obj not in final_assignments[target_court]:
                    final_assignments[target_court].append(player_obj)

            for court_num in final_assignments:
                final_assignments[court_num].sort(key=lambda p: (p.last_name, p.first_name))

            block_data.append({
                'block': block,
                'assignments': dict(final_assignments),
                'has_manual': bool(block_manuals)
            })

    context = {
        'session': session,
        'activities': activities,
        'attendance_form': attendance_form,
        'current_attendees': display_attendees,
        'block_data': block_data,
        'page_title': f"Session Plan: {session}"
    }
    return render(request, 'planning/session_detail.html', context)


def _calculate_skill_priority_groups(players, num_courts):
    skill_order = {
        Player.SkillLevel.ADVANCED: 0,
        Player.SkillLevel.INTERMEDIATE: 1,
        Player.SkillLevel.BEGINNER: 2
    }
    sorted_players = sorted(
        players,
        key=lambda p: (skill_order.get(p.skill_level, 3), p.last_name, p.first_name)
    )
    groups = defaultdict(list)
    if num_courts <= 0:
        return dict(groups)
    for i, player in enumerate(sorted_players):
        court_num = (i % num_courts) + 1
        groups[court_num].append(player)
    return dict(groups)

@login_required
@user_passes_test(is_coach, login_url='login')
def players_list_view(request):
    groups = SchoolGroup.objects.all().order_by('name')
    selected_group_id = request.GET.get('group')
    search_query = request.GET.get('search', '')

    players = Player.objects.filter(is_active=True)

    if selected_group_id:
        players = players.filter(school_groups__id=selected_group_id)
        page_title = f"Players in {get_object_or_404(SchoolGroup, pk=selected_group_id).name}"
    else:
        page_title = "All Active Players"

    if search_query:
        players = players.filter(
            Q(first_name__icontains=search_query) | Q(last_name__icontains=search_query)
        )
        if selected_group_id:
            page_title += f" matching '{search_query}'"
        else:
            page_title = f"Active Players matching '{search_query}'"

    players = players.order_by('last_name', 'first_name').distinct()

    context = {
        'players': players,
        'groups': groups,
        'selected_group_id': selected_group_id,
        'search_query': search_query,
        'page_title': page_title,
    }
    return render(request, 'planning/players_list.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def one_page_plan_view(request, session_id):
    session = get_object_or_404(Session.objects.select_related('school_group').prefetch_related('coaches_attending'), pk=session_id)
    time_blocks = session.time_blocks.order_by('start_offset_minutes')
    activities = ActivityAssignment.objects.filter(
        time_block__session=session
    ).select_related('drill', 'lead_coach').order_by(
        'time_block__start_offset_minutes', 'court_number', 'order'
    )
    coaches = session.coaches_attending.all()

    context = {
        'session': session,
        'time_blocks': time_blocks,
        'activities': activities,
        'coaches': coaches,
    }
    return render(request, 'planning/one_page_plan.html', context)

# --- NEW VIEW FOR SESSION CALENDAR ---
@login_required # Ensure only logged-in users can access
# Add user_passes_test if only staff/coaches should see this
# def coach_check(user):
#     return user.is_staff
# @user_passes_test(coach_check)
def session_calendar_view(request):
    """
    View to display sessions in a calendar format.
    Handles month navigation and prepares data for FullCalendar.
    """
    # Get current configured timezone from Django settings (usually a zoneinfo object)
    current_django_tz = timezone.get_current_timezone() 

    # Determine the month and year to display
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
        if not (1 <= month <= 12):
            month = timezone.now().month 
        current_date_for_nav = date(year, month, 1) # Used for calculating prev/next month links
    except (ValueError, TypeError):
        now_in_current_tz = timezone.now() # Django's timezone.now() is already aware
        year = now_in_current_tz.year
        month = now_in_current_tz.month
        current_date_for_nav = date(year, month, 1)

    # Calculate previous and next month/year for navigation
    prev_month_date = current_date_for_nav - timedelta(days=1) 
    prev_month_date = prev_month_date.replace(day=1)   

    if current_date_for_nav.month == 12:
        next_month_date = date(current_date_for_nav.year + 1, 1, 1)
    else:
        next_month_date = date(current_date_for_nav.year, current_date_for_nav.month + 1, 1)

    sessions_for_month = Session.objects.filter(
        session_date__year=year,
        session_date__month=month
    ).select_related(
        'school_group' 
    ).prefetch_related(
        'coaches_attending', 
        'attendees'          
    ).order_by('session_date', 'session_start_time')

    calendar_events = []
    for session in sessions_for_month:
        # Ensure session_start_time is not None, default to midnight if it is (or handle error)
        s_start_time = session.session_start_time if session.session_start_time else time.min

        # Create a naive datetime object first by combining date and time
        # Use the aliased dt_class for clarity and to avoid conflicts
        naive_start_datetime = dt_class.combine(session.session_date, s_start_time)
        
        # Make the naive datetime timezone-aware using the current Django timezone
        # This assumes that the date and time stored in the database are intended to be in the current_django_tz
        start_datetime_aware = naive_start_datetime.replace(tzinfo=current_django_tz)
        
        # Calculate end datetime
        end_datetime_aware = start_datetime_aware + timedelta(minutes=session.planned_duration_minutes)

        coaches_list = [coach.name for coach in session.coaches_attending.all()]
        if not coaches_list and hasattr(session, 'get_assigned_coaches_display'):
            coaches_list = [session.get_assigned_coaches_display()]

        time_str = s_start_time.strftime('%H:%M')
        school_group_name = session.school_group.name if session.school_group else "No Group"
        event_title = f"{time_str} - {school_group_name}"
        
        event_color = '#d3d3d3' if session.is_cancelled else None 
        text_color = '#a9a9a9' if session.is_cancelled else None 

        calendar_events.append({
            'id': session.pk,
            'title': event_title,
            'start': start_datetime_aware.isoformat(), # FullCalendar expects ISO8601
            'end': end_datetime_aware.isoformat(),     # FullCalendar expects ISO8601
            'allDay': False, 
            'color': event_color, 
            'textColor': text_color, 
            'extendedProps': {
                'school_group_name': school_group_name,
                'session_time_str': f"{s_start_time.strftime('%H:%M')} - {end_datetime_aware.strftime('%H:%M')}",
                'venue_name': session.venue_name if session.venue_name else "N/A",
                'coaches_attending': coaches_list,
                'attendees_count': session.attendees.count(),
                'duration_minutes': session.planned_duration_minutes,
                'is_cancelled_bool': session.is_cancelled,
                'status_display': "Cancelled" if session.is_cancelled else "Scheduled",
                'notes': session.notes if session.notes else "",
                'admin_url': reverse('admin:planning_session_change', args=[session.pk]) if request.user.is_superuser else None,
            }
        })

    context = {
        'calendar_events_json': json.dumps(calendar_events), 
        'current_year': year,
        'current_month': month,
        'current_month_display': current_date_for_nav.strftime('%B %Y'), 
        'prev_year': prev_month_date.year,
        'prev_month': prev_month_date.month,
        'next_year': next_month_date.year,
        'next_month': next_month_date.month,
        'page_title': 'Session Calendar'
    }
    return render(request, 'planning/session_calendar.html', context)


# --- NEW VIEW FOR EXPORTING WEEKLY SCHEDULE TO CSV ---
@login_required # Ensure only logged-in users can access
# @user_passes_test(some_staff_check_function) # Optional: Restrict to staff/superusers
def export_weekly_schedule_view(request):
    """
    Exports the weekly session schedule as a CSV file.
    Accepts 'year', 'month', and 'day' GET parameters to determine the week.
    Defaults to the current week if parameters are not provided or invalid.
    """
    try:
        # Get year, month, day from GET parameters. Default to today if not present or invalid.
        year_str = request.GET.get('year')
        month_str = request.GET.get('month')
        day_str = request.GET.get('day')

        if year_str and month_str and day_str:
            target_date = date(int(year_str), int(month_str), int(day_str))
        else:
            # Default to today's date if parameters are missing
            target_date = timezone.localdate() # Use timezone.localdate() for current local date

    except (ValueError, TypeError):
        # Handle invalid date parameters by defaulting to today
        target_date = timezone.localdate()

    # Get the weekly session data using the helper function
    weekly_data = get_weekly_session_data(target_date)
    sessions_data = weekly_data.get('sessions_data', [])
    week_start_str = weekly_data.get('week_start_date', target_date).strftime('%Y-%m-%d')

    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="weekly_schedule_{week_start_str}.csv"'},
    )

    writer = csv.writer(response)
    # Write the header row for the CSV
    writer.writerow(['Date', 'Day', 'Time Slot', 'Class Name', 'Coaches', 'Venue', 'Status'])

    # Write session data rows
    if sessions_data:
        for session_dict in sessions_data:
            writer.writerow([
                session_dict.get('date', ''),
                session_dict.get('day', ''),
                session_dict.get('time_slot', ''),
                session_dict.get('class_name', ''),
                session_dict.get('coaches', ''),
                session_dict.get('venue', ''),
                session_dict.get('status', '')
            ])
    else:
        # Optional: Write a message if no sessions are found for the week
        writer.writerow(['No sessions found for the week starting', week_start_str, '', '', '', '', ''])

    return response

@login_required
@user_passes_test(lambda u: u.is_superuser) # Only superusers can toggle visibility
@require_POST # Ensure this action is only done via POST for safety
def toggle_assessment_visibility(request, assessment_id):
    """
    Toggles the is_hidden status of a SessionAssessment.
    Only accessible by superusers.
    """
    assessment = get_object_or_404(SessionAssessment, pk=assessment_id)
    assessment.is_hidden = not assessment.is_hidden
    assessment.save()

    if assessment.is_hidden:
        messages.success(request, f"Assessment for {assessment.player.full_name} on {assessment.session.session_date.strftime('%Y-%m-%d')} is now hidden.")
    else:
        messages.success(request, f"Assessment for {assessment.player.full_name} on {assessment.session.session_date.strftime('%Y-%m-%d')} is now visible.")
    
    # Redirect back to the player's profile page
    return redirect('planning:player_profile', player_id=assessment.player.id)