# planning/views.py

import json
from datetime import datetime as dt_class, timedelta, date as date_obj, time 
from collections import defaultdict 
import calendar 

from django.conf import settings 
from django.contrib import messages
from django.contrib.auth import get_user_model 
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import FieldError, ObjectDoesNotExist 
from django.db.models import Q, Prefetch, Count, Exists, OuterRef, Avg, F 
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, Http404 
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST 
from .utils import get_weekly_session_data 
import csv 
from .notifications import verify_confirmation_token 
from django.forms import inlineformset_factory
from .live_session_utils import _calculate_skill_priority_groups
from ics import Calendar, Event
from .utils import get_month_start_end, get_month_choices, get_year_choices
from .notifications import send_availability_change_alert_to_admins

User = get_user_model()

from .models import (
    Session, SchoolGroup, Player, Coach, Drill, TimeBlock,
    ActivityAssignment, SessionAssessment, CourtSprintRecord,
    VolleyRecord, BackwallDriveRecord, MatchResult,
    ManualCourtAssignment, CoachFeedback, CoachAvailability,
    CoachSessionCompletion, ScheduledClass, Venue, GroupAssessment, Coach, 
    Event
)

try:
    from solosync_api.models import SoloSessionLog, SoloRoutine
    solosync_imported = True
except ImportError:
    print("Warning: Could not import SoloSync models. SoloSync features will be disabled.")
    SoloSessionLog = None
    SoloRoutine = None
    solosync_imported = False

from .forms import (
    AttendanceForm, ActivityAssignmentForm, SessionAssessmentForm,
    CoachFeedbackForm, CourtSprintRecordForm, VolleyRecordForm,
    BackwallDriveRecordForm, MatchResultForm, GroupAssessmentForm, AttendancePeriodFilterForm, MonthYearFilterForm
)

from django import forms

class MonthYearSelectionForm(forms.Form):
    month = forms.ChoiceField()
    year = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        initial_data = kwargs.pop('initial', None) 
        super().__init__(*args, **kwargs)
        now = timezone.now()
        form_current_year = now.year
        form_current_month = now.month 
        
        year_choices = [(year, str(year)) for year in range(form_current_year -1, form_current_year + 3)] 
        month_choices = [(i, date_obj(form_current_year, i, 1).strftime('%B')) for i in range(1, 13)] 

        self.fields['year'].choices = year_choices
        self.fields['year'].initial = initial_data.get('year', form_current_year) if initial_data else form_current_year

        self.fields['month'].choices = month_choices
        self.fields['month'].initial = initial_data.get('month', form_current_month) if initial_data else form_current_month

def is_coach(user): 
    return user.is_authenticated and user.is_staff

def is_superuser(user): 
    return user.is_authenticated and user.is_superuser

@login_required
@user_passes_test(is_superuser, login_url='login') 
def coach_completion_report_view(request):
    today = timezone.now().date()
    if request.method == 'POST':
        completion_id = request.POST.get('completion_id')
        action = request.POST.get('action')
        redirect_month_str = request.POST.get('filter_month')
        redirect_year_str = request.POST.get('filter_year')
        redirect_url = reverse('planning:coach_completion_report')
        query_params = {}
        if redirect_month_str and redirect_year_str:
            try:
                query_params['month'] = int(redirect_month_str)
                query_params['year'] = int(redirect_year_str)
                redirect_url += f'?month={query_params["month"]}&year={query_params["year"]}'
            except ValueError: 
                messages.warning(request, "Could not preserve filter due to invalid month/year in POST.")
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
        except ValueError: 
            messages.error(request, "Invalid ID format.")
        except CoachSessionCompletion.DoesNotExist: 
            messages.error(request, "Completion record not found.")
        except Exception as e: 
            messages.error(request, f"An error occurred: {e}")
            print(f"Error in coach_completion_report_view POST: {e}")
        return redirect(redirect_url)

    first_day_of_current_month = today.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    default_target_year = last_day_of_previous_month.year
    default_target_month = last_day_of_previous_month.month
    try:
        target_year = int(request.GET.get('year', default_target_year))
        target_month = int(request.GET.get('month', default_target_month))
    except ValueError:
        messages.warning(request, "Invalid month/year parameters. Displaying report for the default period (previous month).")
        target_year = default_target_year
        target_month = default_target_month
    
    year_choices = [today.year - i for i in range(3)]
    if target_year not in year_choices and target_year < today.year : 
        year_choices.append(target_year)
        year_choices.sort(reverse=True)
    elif target_year > today.year : 
        messages.warning(request, "Future year selected, reverting to default period.")
        target_year = default_target_year
        target_month = default_target_month
    
    month_name_choices = [{'value': i, 'name': calendar.month_name[i]} for i in range(1, 13)]
    if not (1 <= target_month <= 12):
        messages.warning(request, f"Invalid month ({target_month}) selected. Reverting to default period.")
        target_year = default_target_year
        target_month = default_target_month
    
    available_months_combined = []
    current_loop_date = today.replace(day=1) 
    for _ in range(12): 
        available_months_combined.append({
            'year': current_loop_date.year, 
            'month': current_loop_date.month, 
            'name': current_loop_date.strftime('%B %Y')
        })
        current_loop_date = (current_loop_date - timedelta(days=1)).replace(day=1)
    
    _, num_days = calendar.monthrange(target_year, target_month)
    start_date = date_obj(target_year, target_month, 1)
    end_date = date_obj(target_year, target_month, num_days)

    completion_records = CoachSessionCompletion.objects.filter(
        session__session_date__gte=start_date, 
        session__session_date__lte=end_date
    ).select_related(
        'coach', 'coach__user', 'session', 'session__school_group'
    ).order_by(
        'session__session_date', 'session__session_start_time', 'coach__name'
    )
    context = {
        'completion_records': completion_records, 
        'selected_year': target_year, 
        'selected_month': target_month, 
        'year_choices': year_choices, 
        'month_name_choices': month_name_choices, 
        'available_months_combined': available_months_combined, 
        'start_date': start_date, 
        'end_date': end_date, 
        'page_title': f"Coach Completion Report ({start_date.strftime('%B %Y')})"
    }
    return render(request, 'planning/coach_completion_report.html', context)

@login_required
@user_passes_test(is_superuser, login_url='login') 
def session_staffing_view(request):
    # --- POST request handling remains the same ---
    if request.method == 'POST':
        # ... (Your existing POST logic for updating assignments)
        # No changes needed here for this feature
        session_id = request.POST.get('session_id')
        assigned_coach_ids_str = request.POST.getlist(f'coaches_for_session_{session_id}')
        if not session_id: 
            messages.error(request, "Invalid request: Missing session ID.")
            return redirect('planning:session_staffing')
        try:
            session_to_update = get_object_or_404(Session, pk=int(session_id))
            previously_assigned_coach_users = {coach.user for coach in session_to_update.coaches_attending.all() if coach.user}
            selected_coaches_qs = Coach.objects.none() 
            if assigned_coach_ids_str:
                valid_coach_ids = [int(cid) for cid in assigned_coach_ids_str if cid.isdigit()]
                if valid_coach_ids: 
                    selected_coaches_qs = Coach.objects.filter(pk__in=valid_coach_ids)
            session_to_update.coaches_attending.set(selected_coaches_qs) 
            messages.success(request, f"Coach assignments updated for session on {session_to_update.session_date.strftime('%d %b %Y')}.")
            current_assigned_coach_users = {coach.user for coach in selected_coaches_qs if coach.user}
            for coach_user_assigned in current_assigned_coach_users:
                is_newly_assigned = coach_user_assigned not in previously_assigned_coach_users
                existing_availability = CoachAvailability.objects.filter(coach=coach_user_assigned, session=session_to_update).first()
                should_reset_availability = False
                if is_newly_assigned and existing_availability: 
                    if existing_availability.is_available is False: 
                        should_reset_availability = True
                elif not is_newly_assigned and existing_availability and existing_availability.is_available is False: 
                    should_reset_availability = True
                if should_reset_availability and existing_availability:
                    existing_availability.delete()
                    messages.info(request, f"Coach {coach_user_assigned.username}'s previous availability for session on {session_to_update.session_date.strftime('%d %b')} has been reset due to reassignment.")
        except (ValueError, Session.DoesNotExist): 
            messages.error(request, "Invalid session or data.")
        except Exception as e: 
            messages.error(request, f"An error occurred: {e}")
            print(f"Error in session_staffing_view POST: {e}")
        return redirect(f"{reverse('planning:session_staffing')}?week={request.GET.get('week', '0')}")


    # --- GET request handling with week navigation and updated logic ---
    now = timezone.now()
    today = now.date()
    
    try:
        week_offset = int(request.GET.get('week', '0'))
    except (ValueError, TypeError):
        week_offset = 0

    start_of_this_week = today - timedelta(days=today.weekday())
    target_week_start = start_of_this_week + timedelta(weeks=week_offset)
    target_week_end = target_week_start + timedelta(days=6)

    sessions_in_week_qs = Session.objects.filter(
        session_date__gte=target_week_start,
        session_date__lte=target_week_end,
        is_cancelled=False
    ).select_related('school_group', 'venue').prefetch_related(
        'coaches_attending__user',
        Prefetch(
            'coach_availabilities',
            queryset=CoachAvailability.objects.select_related('coach'),
            to_attr='availability_details_for_session'
        )
    ).order_by('session_date', 'session_start_time')
    
    all_active_coaches = list(Coach.objects.filter(is_active=True).select_related('user').order_by('name'))
    
    # Group sessions by day
    grouped_sessions = {i: [] for i in range(7)}
    for session_obj in sessions_in_week_qs:
        # Assigned Coaches logic (remains the same)
        assigned_coaches_with_status = []
        has_pending_confirmations_for_session = False
        has_declined_coaches_for_session = False
        for coach_profile_item in session_obj.coaches_attending.all():
            # ... (your existing logic for assigned coaches)
            coach_user_item = coach_profile_item.user
            status = "Pending Response"; availability_notes = ""; is_confirmed = False; is_declined = False
            if coach_user_item: 
                for availability_detail in session_obj.availability_details_for_session:
                    if availability_detail.coach_id == coach_user_item.id:
                        if availability_detail.is_available is True: status = "Confirmed"; is_confirmed = True
                        elif availability_detail.is_available is False: status = "Declined"; is_declined = True; has_declined_coaches_for_session = True
                        availability_notes = availability_detail.notes; break
                if status == "Pending Response": has_pending_confirmations_for_session = True
            assigned_coaches_with_status.append({'coach_profile': coach_profile_item, 'status': status, 'is_confirmed': is_confirmed, 'is_declined': is_declined, 'notes': availability_notes})

        # +++ UPDATED: Logic for Available Coaches +++
        available_coaches_for_assignment_display = []
        for avail_detail in session_obj.availability_details_for_session:
            # We only care about coaches who have marked themselves as available
            if avail_detail.is_available is not True:
                continue

            # Find the corresponding Coach profile instance
            coach_instance = next((c for c in all_active_coaches if c.user and c.user.id == avail_detail.coach_id), None)
            if not coach_instance:
                continue

            # Check for "Emergency only" note
            is_emergency_only = "emergency" in avail_detail.notes.lower()

            available_coaches_for_assignment_display.append({
                'coach_profile': coach_instance,
                'notes': avail_detail.notes,
                'is_emergency_only': is_emergency_only
            })
        
        # Sort the list: fully available first, then emergency only
        available_coaches_for_assignment_display.sort(key=lambda x: x['is_emergency_only'])
        # +++ END UPDATED Logic +++

        session_data = {
            'session_obj': session_obj,
            'assigned_coaches_with_status': assigned_coaches_with_status,
            'available_coaches_for_assignment': available_coaches_for_assignment_display,
            'has_pending_confirmations': has_pending_confirmations_for_session,
            'has_declined_coaches': has_declined_coaches_for_session
        }
        grouped_sessions[session_obj.session_date.weekday()].append(session_data)

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    display_week = []
    for i in range(5): # Monday to Friday
        day_date = target_week_start + timedelta(days=i)
        display_week.append({
            'day_name': day_names[i],
            'date': day_date,
            'sessions': grouped_sessions.get(i, [])
        })

    context = {
        'page_title': "Session Staffing",
        'all_coaches_for_form': all_active_coaches,
        'display_week': display_week,
        'week_start': target_week_start,
        'week_end': target_week_end,
        'current_week_offset': week_offset,
        'next_week_offset': week_offset + 1,
        'prev_week_offset': week_offset - 1,
    }
    return render(request, 'planning/session_staffing.html', context)

@login_required
@user_passes_test(is_coach, login_url='login')
def my_availability_view(request):
    try:
        coach_profile = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        messages.error(request, "Your user account is not linked to a Coach profile.")
        return redirect('homepage')

    if request.method == 'POST':
        updated_count = 0
        for key, value in request.POST.items():
            if key.startswith('availability_session_'):
                session_id = key.split('_')[-1]
                notes_key = f'notes_session_{session_id}' # Corresponding notes field
                notes = request.POST.get(notes_key, '').strip()

                try:
                    session = Session.objects.get(pk=session_id)
                    is_assigned = coach_profile in session.coaches_attending.all()
                    
                    # Check if status is being set to UNAVAILABLE for an assigned session
                    if is_assigned and value == 'UNAVAILABLE':
                        if not notes:
                            # Backend validation: Reason is required
                            messages.error(request, f"A reason is required to mark yourself unavailable for the assigned session on {session.session_date.strftime('%d %b')}.")
                            continue # Skip this update and process the next item
                        else:
                            # Reason provided, trigger email alert
                            send_availability_change_alert_to_admins(session=session, coach=coach_profile, reason=notes)

                    # Proceed with saving the availability status
                    is_available = None
                    if value == 'AVAILABLE' or value == 'EMERGENCY':
                        is_available = True
                    elif value == 'UNAVAILABLE':
                        is_available = False
                    
                    if value != 'NO_CHANGE':
                        CoachAvailability.objects.update_or_create(
                            coach=request.user, session=session,
                            defaults={'is_available': is_available, 'notes': notes, 'status_updated_at': timezone.now()}
                        )
                        updated_count += 1
                
                except Session.DoesNotExist:
                    messages.warning(request, f"Could not find session with ID {session_id} to update.")
        
        if updated_count > 0:
            messages.success(request, f"Successfully updated your availability for {updated_count} session(s).")
        
        return redirect(f"{reverse('planning:my_availability')}?week={request.GET.get('week', '0')}")


    # The GET request logic remains the same as our working version
    # ... (the rest of the view from the previous working step)
    now = timezone.now()
    today = now.date()
    
    try: week_offset = int(request.GET.get('week', '0'))
    except (ValueError, TypeError): week_offset = 0

    start_of_this_week = today - timedelta(days=today.weekday())
    target_week_start = start_of_this_week + timedelta(weeks=week_offset)
    target_week_end = target_week_start + timedelta(days=6)

    upcoming_sessions_qs = Session.objects.filter(
        session_date__gte=target_week_start,
        session_date__lte=target_week_end,
        is_cancelled=False
    ).select_related('school_group', 'venue').prefetch_related(
        'coaches_attending',
        Prefetch('coach_availabilities', queryset=CoachAvailability.objects.filter(coach=request.user), to_attr='my_availability')
    ).order_by('session_date', 'session_start_time')
    
    grouped_sessions = {i: [] for i in range(7)}
    for session in upcoming_sessions_qs:
        availability_info = session.my_availability[0] if session.my_availability else None
        current_status = 'NO_CHANGE'
        if availability_info:
            if availability_info.is_available and "emergency" in availability_info.notes.lower(): current_status = 'EMERGENCY'
            elif availability_info.is_available is True: current_status = 'AVAILABLE'
            elif availability_info.is_available is False: current_status = 'UNAVAILABLE'
        session_data = {
            'session_obj': session, 'current_status': current_status,
            'is_assigned': coach_profile in session.coaches_attending.all(),
            'group_description': session.school_group.description if session.school_group else ""
        }
        grouped_sessions[session.session_date.weekday()].append(session_data)

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    display_week = []
    for i in range(5):
        day_date = target_week_start + timedelta(days=i)
        display_week.append({'day_name': day_names[i], 'date': day_date, 'sessions': grouped_sessions.get(i, [])})

    context = {
        'page_title': "My Availability", 'display_week': display_week, 'week_start': target_week_start,
        'week_end': target_week_end, 'current_week_offset': week_offset,
        'next_week_offset': week_offset + 1, 'prev_week_offset': week_offset - 1,
    }
    return render(request, 'planning/my_availability.html', context)

@login_required
@user_passes_test(is_coach, login_url='login')
def homepage_view(request):
    now = timezone.now()
    today = now.date()
    user = request.user
    coach_profile = None
    
    context = {
        'upcoming_sessions': Session.objects.none(),
        'recent_sessions_for_feedback': [], 
        'recent_solo_logs': [],
        'unstaffed_session_count': 0,
        'all_coach_assessments': None, 
        'recent_group_assessments': None,
        'unconfirmed_staffing_alerts': [],
        'sessions_for_direct_confirmation': [],
        'page_title': "Dashboard"
    }

    upcoming_sessions_base_qs = Session.objects.filter(
        Q(session_date__gt=today) | Q(session_date=today, session_start_time__gte=now.time()),
        is_cancelled=False
    ).select_related('school_group', 'venue').order_by('session_date', 'session_start_time')

    if user.is_superuser:
        context['page_title'] = "Admin Dashboard"
        context['upcoming_sessions'] = upcoming_sessions_base_qs[:5]
        
        context['all_coach_assessments'] = SessionAssessment.objects.filter(
            superuser_reviewed=False 
        ).select_related(
            'player', 'session', 'session__school_group', 'submitted_by', 'session__venue'
        ).order_by('-date_recorded', '-session__session_date')[:20]

        context['recent_group_assessments'] = GroupAssessment.objects.filter(
            superuser_reviewed=False
        ).select_related(
            'session', 'session__school_group', 'assessing_coach', 'session__venue'
        ).order_by('-assessment_datetime')[:10] 
        
        two_weeks_from_now = today + timedelta(weeks=2)
        unstaffed_sessions = Session.objects.filter(
            session_date__gte=today, 
            session_date__lte=two_weeks_from_now, 
            coaches_attending__isnull=True, 
            is_cancelled=False
        ).distinct()
        context['unstaffed_session_count'] = unstaffed_sessions.count()
        
        critical_timeframe_end = now + timedelta(hours=48) 
        sessions_needing_attention = Session.objects.filter(
            session_date__gte=today, 
            session_date__lte=critical_timeframe_end.date(), 
            is_cancelled=False, 
            coaches_attending__isnull=False 
        ).prefetch_related(
            'coaches_attending__user', 
            Prefetch('coach_availabilities', queryset=CoachAvailability.objects.select_related('coach'), to_attr='all_coach_availabilities_for_session')
        ).distinct()
        
        alerts = []
        for session in sessions_needing_attention:
            if session.session_date == critical_timeframe_end.date() and session.session_start_time > critical_timeframe_end.time(): 
                continue
            
            unconfirmed_coaches_for_this_session = []
            assigned_coaches_on_session = list(session.coaches_attending.all()) 
            # Ensure that avail.coach is a User instance, which it should be due to select_related('coach') on CoachAvailability query
            availability_map = {avail.coach.id: avail for avail in session.all_coach_availabilities_for_session} # <<< CORRECTED HERE

            for coach_profile_assigned in assigned_coaches_on_session:
                coach_user_assigned = coach_profile_assigned.user
                if not coach_user_assigned: 
                    continue

                availability_record = availability_map.get(coach_user_assigned.id) # Use coach_user_assigned.id here
                
                if not availability_record or availability_record.is_available is None: 
                    status = "Pending Response"
                    notes = availability_record.notes if availability_record else ""
                    unconfirmed_coaches_for_this_session.append({'name': coach_user_assigned.get_full_name() or coach_user_assigned.username, 'status': status, 'notes': notes})
                elif availability_record.is_available is False: 
                    status = "Declined"
                    notes = availability_record.notes
                    unconfirmed_coaches_for_this_session.append({'name': coach_user_assigned.get_full_name() or coach_user_assigned.username, 'status': status, 'notes': notes})
            
            if unconfirmed_coaches_for_this_session: 
                alerts.append({'session': session, 'unconfirmed_coaches': unconfirmed_coaches_for_this_session})
        context['unconfirmed_staffing_alerts'] = alerts

    elif user.is_staff: 
        context['page_title'] = "Coach Dashboard"
        try:
            if hasattr(user, 'coach_profile') and user.coach_profile:
                coach_profile = user.coach_profile
            else:
                coach_profile = Coach.objects.get(user=user)
            
            if coach_profile:
                context['upcoming_sessions'] = upcoming_sessions_base_qs.filter(
                    coaches_attending=coach_profile
                )[:5]
                
                tomorrow = today + timedelta(days=1)
                sessions_for_confirmation_qs = Session.objects.filter(
                    session_date=tomorrow,
                    coaches_attending=coach_profile,
                    is_cancelled=False
                ).select_related('school_group', 'venue').distinct().order_by('session_start_time')

                sessions_for_direct_confirmation_list = []
                for sess_confirm in sessions_for_confirmation_qs:
                    current_avail = CoachAvailability.objects.filter(session=sess_confirm, coach=user).first()
                    if not (current_avail and current_avail.is_available is True):
                        sessions_for_direct_confirmation_list.append({
                            'session': sess_confirm,
                            'current_status_is_declined': current_avail.is_available is False if current_avail else False,
                            'current_notes': current_avail.notes if current_avail else ""
                        })
                context['sessions_for_direct_confirmation'] = sessions_for_direct_confirmation_list
                
                date_limit_past_reminders = today - timedelta(weeks=4)

                coached_ended_sessions = Session.objects.filter(
                    coaches_attending=coach_profile,
                    session_date__gte=date_limit_past_reminders,
                    session_date__lte=today,
                    is_cancelled=False
                ).filter(
                    Q(session_date__lt=today) | Q(session_date=today, session_start_time__lt=now.time())
                ).select_related('school_group'
                ).prefetch_related(
                    'attendees',
                    Prefetch(
                        'session_assessments',
                        queryset=SessionAssessment.objects.filter(submitted_by=user),
                        to_attr='my_player_assessments_for_session'
                    ),
                    Prefetch(
                        'group_assessments',
                        queryset=GroupAssessment.objects.filter(assessing_coach=user),
                        to_attr='my_group_assessment_for_session' 
                    ),
                    Prefetch( 
                        'coach_completions',
                        queryset=CoachSessionCompletion.objects.filter(coach=coach_profile, assessments_submitted=True),
                        to_attr='coach_marked_player_assessments_complete'
                    )
                ).distinct().order_by('-session_date', '-session_start_time')

                sessions_needing_any_feedback = []
                for session in coached_ended_sessions:
                    player_assessments_pending = False
                    marked_complete_by_coach = bool(session.coach_marked_player_assessments_complete)

                    if not marked_complete_by_coach:
                        if session.attendees.exists():
                            assessed_player_ids_for_this_coach = {
                                sa.player_id for sa in session.my_player_assessments_for_session
                            }
                            for attendee in session.attendees.all():
                                if attendee.id not in assessed_player_ids_for_this_coach:
                                    player_assessments_pending = True
                                    break
                    
                    group_assessment_done = bool(session.my_group_assessment_for_session)

                    if player_assessments_pending or not group_assessment_done:
                        sessions_needing_any_feedback.append(session)
                        if len(sessions_needing_any_feedback) >= 5:
                            break
                
                context['recent_sessions_for_feedback'] = sessions_needing_any_feedback

        except Coach.DoesNotExist:
            messages.warning(request, "Your user account is not linked to a Coach profile.")
        except Exception as e: 
            messages.error(request, f"Could not load dashboard data: {str(e)}")
            
    # SoloSync Logs
    solosync_imported = 'solosync_api' in settings.INSTALLED_APPS
    SoloSessionLog = None
    if solosync_imported:
        try:
            from solosync_api.models import SoloSessionLog
        except ImportError:
            solosync_imported = False
            SoloSessionLog = None
    
    if solosync_imported and SoloSessionLog is not None:
        try:
            context['recent_solo_logs'] = SoloSessionLog.objects.select_related(
                'player', 'routine'
            ).order_by('-completed_at')[:10]
        except FieldError as e:
            print(f"FieldError fetching SoloSessionLog: {e}") 
        except Exception as e:
            print(f"Error fetching SoloSessionLog: {e}")

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
        'form': form, 'time_block': time_block, 'session': session, 
        'court_num': court_num, 'page_title': 'Add Activity'
    }
    return render(request, 'planning/add_activity_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def edit_activity(request, activity_id):
    activity_instance = get_object_or_404(ActivityAssignment.objects.select_related('time_block__session'), pk=activity_id)
    session = activity_instance.time_block.session
    can_edit = False
    if request.user.is_superuser: 
        can_edit = True
    else:
        try:
            coach_profile_instance = None
            if hasattr(request.user, 'coach_profile') and request.user.coach_profile:
                coach_profile_instance = request.user.coach_profile
            else:
                coach_profile_instance = Coach.objects.filter(user=request.user).first()
            
            if coach_profile_instance and coach_profile_instance in session.coaches_attending.all():
                can_edit = True
        except AttributeError: 
            pass 
    if not can_edit: 
        messages.error(request, "You do not have permission to edit this activity.")
        return redirect('planning:session_detail', session_id=session.id)
    
    if request.method == 'POST':
        form = ActivityAssignmentForm(request.POST, instance=activity_instance)
        if form.is_valid(): 
            form.save()
            messages.success(request, "Activity updated successfully.")
            return redirect('planning:session_detail', session_id=session.id)
    else: 
        form = ActivityAssignmentForm(instance=activity_instance)
    context = {
        'form': form, 'activity_instance': activity_instance, 
        'time_block': activity_instance.time_block, 'session': session, 
        'court_num': activity_instance.court_number, 'page_title': 'Edit Activity'
    }
    return render(request, 'planning/add_activity_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
@require_POST
def delete_activity(request, activity_id):
    activity_instance = get_object_or_404(ActivityAssignment.objects.select_related('time_block__session'), pk=activity_id)
    session = activity_instance.time_block.session
    session_id_for_redirect = session.id
    can_delete = False
    if request.user.is_superuser: 
        can_delete = True
    else:
        try:
            coach_profile_instance = None
            if hasattr(request.user, 'coach_profile') and request.user.coach_profile:
                coach_profile_instance = request.user.coach_profile
            else:
                coach_profile_instance = Coach.objects.filter(user=request.user).first()

            if coach_profile_instance and coach_profile_instance in session.coaches_attending.all():
                can_delete = True
        except AttributeError: 
            pass
    if not can_delete: 
        messages.error(request, "You do not have permission to delete this activity.")
        return redirect('planning:session_detail', session_id=session_id_for_redirect)
    
    activity_name = str(activity_instance)
    activity_instance.delete()
    messages.success(request, f"Activity '{activity_name}' deleted successfully.")
    return redirect('planning:session_detail', session_id=session_id_for_redirect)


@login_required
@user_passes_test(is_coach, login_url='login')
def player_profile(request, player_id):
    player = get_object_or_404(Player.objects.prefetch_related('school_groups'), pk=player_id)
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
            attendance_percentage = None 
    
    assessments_base_qs = player.session_assessments_by_player.select_related(
        'session', 'session__school_group', 'submitted_by'
    ).order_by('-date_recorded', '-session__session_start_time')
    
    if request.user.is_superuser: 
        assessments = assessments_base_qs.all()
    elif request.user.is_staff: 
        assessments = assessments_base_qs.filter(is_hidden=False)
    else: 
        assessments = player.session_assessments_by_player.none() 
    
    sprints = player.sprint_records.select_related('session').order_by('date_recorded')
    volleys = player.volley_records.select_related('session').order_by('date_recorded')
    drives = player.drive_records.select_related('session').order_by('date_recorded')
    matches = player.match_results.select_related('session').order_by('-date')

    sprint_chart_data = defaultdict(lambda: {'labels': [], 'data': []})
    for sprint in sprints: 
        key = sprint.duration_choice
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
        'player': player, 'sessions_attended': sessions_attended_qs, 
        'attended_sessions_count': attended_sessions_count, 
        'total_relevant_sessions_count': total_relevant_sessions_count, 
        'attendance_percentage': attendance_percentage, 'assessments': assessments, 
        'sprints': sprints, 'volleys': volleys, 'drives': drives, 'matches': matches, 
        'sprint_chart_data': dict(sprint_chart_data), 
        'volley_chart_data': dict(volley_chart_data), 
        'drive_chart_data': dict(drive_chart_data)
    }
    return render(request, 'planning/player_profile.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def assess_player_session(request, session_id, player_id):
    session = get_object_or_404(Session, pk=session_id)
    player = get_object_or_404(Player, pk=player_id)
    assessment_instance = SessionAssessment.objects.filter(
        session=session, player=player, submitted_by=request.user
    ).first()
    if assessment_instance: 
        messages.info(request, f"You have already submitted an assessment for {player.full_name} for this session. Editing existing assessment.")
        return redirect('planning:edit_session_assessment', assessment_id=assessment_instance.id)
    
    if request.method == 'POST':
        form = SessionAssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.session = session
            assessment.player = player
            assessment.submitted_by = request.user
            if not form.cleaned_data.get('date_recorded'): 
                assessment.date_recorded = session.session_date
            assessment.save()
            messages.success(request, f"Assessment added for {player.full_name} in session on {session.session_date.strftime('%d %b')}.")
            coach_profile = None
            try:
                if hasattr(request.user, 'coach_profile') and request.user.coach_profile: 
                    coach_profile = request.user.coach_profile
                else: 
                    coach_profile = Coach.objects.get(user=request.user)
                if coach_profile:
                    completion, created = CoachSessionCompletion.objects.update_or_create(
                        coach=coach_profile, session=session, defaults={'confirmed_for_payment': True}
                    )
                    print(f"Marked payment confirmed (new assessment) for {coach_profile.name} for session {session.id}. CSC Created: {created}")
                else: 
                    print(f"Could not find Coach profile for user {request.user.username} (new assessment).")
            except Coach.DoesNotExist: 
                print(f"Coach.DoesNotExist for user {request.user.username}.")
            except Exception as e: 
                print(f"Error updating CoachSessionCompletion (new assessment): {e}")
            return redirect('planning:pending_assessments') 
    else: 
        form = SessionAssessmentForm(initial={'date_recorded': session.session_date}) 
    
    context = {
        'form': form, 'session': session, 'player': player, 
        'assessment_instance': None, 
        'page_title': f"Add Assessment for {player.full_name} ({session.session_date.strftime('%d %b')})"
    }
    return render(request, 'planning/assess_player_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def edit_session_assessment(request, assessment_id):
    assessment_instance = get_object_or_404(SessionAssessment.objects.select_related('player', 'session', 'submitted_by'), pk=assessment_id)
    player = assessment_instance.player
    session = assessment_instance.session
    original_submitter = assessment_instance.submitted_by 
    if not (request.user.is_superuser or original_submitter == request.user): 
        messages.error(request, "You do not have permission to edit this assessment.")
        return redirect('planning:player_profile', player_id=player.id)
    
    if request.method == 'POST':
        form = SessionAssessmentForm(request.POST, instance=assessment_instance)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.submitted_by = original_submitter
            assessment.save()
            messages.success(request, f"Assessment for {player.full_name} (Session: {session.session_date.strftime('%d %b')}) updated.")
            if original_submitter: 
                coach_profile = None
                try:
                    if hasattr(original_submitter, 'coach_profile') and original_submitter.coach_profile: 
                        coach_profile = original_submitter.coach_profile
                    else: 
                        coach_profile = Coach.objects.get(user=original_submitter)
                    if coach_profile:
                        completion, created = CoachSessionCompletion.objects.update_or_create(
                            coach=coach_profile, session=session, defaults={'confirmed_for_payment': True}
                        ) 
                        if created and completion.assessments_submitted: 
                            print(f"Warning: New CSC for {coach_profile.name}, session {session.id} had assessments_submitted=True on edit path")
                        print(f"Marked payment confirmed (on edit) for {coach_profile.name} for session {session.id}")
                    else: 
                        print(f"Could not find Coach profile for user {original_submitter.username} (on edit).")
                except Coach.DoesNotExist: 
                    print(f"Coach.DoesNotExist for user {original_submitter.username} (on edit).")
                except Exception as e: 
                    print(f"Error updating CoachSessionCompletion (on edit): {e}")
            return redirect('planning:player_profile', player_id=player.id)
    else: 
        form = SessionAssessmentForm(instance=assessment_instance)
    
    context = {
        'form': form, 'session': session, 'player': player, 
        'assessment_instance': assessment_instance, 
        'page_title': f'Edit Assessment for {player.full_name}'
    }
    return render(request, 'planning/assess_player_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
@require_POST 
def delete_session_assessment(request, assessment_id):
    assessment_instance = get_object_or_404(SessionAssessment.objects.select_related('player', 'submitted_by'), pk=assessment_id)
    player = assessment_instance.player
    original_submitter = assessment_instance.submitted_by
    if not (request.user.is_superuser or original_submitter == request.user): 
        messages.error(request, "You do not have permission to delete this assessment.")
        return redirect('planning:player_profile', player_id=player.id)
    assessment_instance.delete()
    messages.success(request, "Session assessment deleted successfully.")
    return redirect('planning:player_profile', player_id=player.id)


@login_required
@user_passes_test(is_coach, login_url='login')
def assess_latest_session_redirect(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    latest_session = player.attended_sessions.order_by('-session_date', '-session_start_time').first()
    if latest_session:
        assessment_instance = SessionAssessment.objects.filter(
            session=latest_session, player=player, submitted_by=request.user
        ).first() 
        if assessment_instance: 
            return redirect('planning:edit_session_assessment', assessment_id=assessment_instance.id)
        else: 
            return redirect('planning:assess_player_session', session_id=latest_session.id, player_id=player.id)
    else: 
        messages.warning(request, f"{player.full_name} has no recorded session attendance to assess.")
        return redirect('planning:player_profile', player_id=player.id)


@login_required
@user_passes_test(is_coach, login_url='login')
@require_POST 
def mark_my_assessments_complete_for_session_view(request, session_id):
    coach_profile = None
    try:
        if hasattr(request.user, 'coach_profile') and request.user.coach_profile: 
            coach_profile = request.user.coach_profile
        else: 
            coach_profile = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist: 
        messages.error(request, "Your coach profile could not be found.")
        return redirect('planning:pending_assessments')
    except AttributeError: 
        if request.user.is_superuser: 
            messages.error(request, "Superuser account not linked to a Coach profile for this action.")
        else: 
            messages.error(request, "Could not determine your coach identity.")
        return redirect('planning:pending_assessments')
    
    if not coach_profile: 
        messages.error(request, "Coach profile not loaded.")
        return redirect('planning:pending_assessments')
    
    session_to_update = get_object_or_404(Session, pk=session_id)
    if not session_to_update.coaches_attending.filter(pk=coach_profile.pk).exists(): 
        messages.error(request, "You are not assigned to this session.")
        return redirect('planning:pending_assessments')
    
    has_submitted_one = SessionAssessment.objects.filter(
        session=session_to_update, submitted_by=request.user
    ).exists()
    
    completion_record, created = CoachSessionCompletion.objects.get_or_create(
        coach=coach_profile, 
        session=session_to_update, 
        defaults={'assessments_submitted': False, 'confirmed_for_payment': False}
    )
    
    if not completion_record.assessments_submitted:
        completion_record.assessments_submitted = True
        completion_record.save()
        messages.success(request, f"Your assessments for session on {session_to_update.session_date.strftime('%d %b %Y')} marked as complete.")
    else: 
        messages.info(request, f"Your assessments for session on {session_to_update.session_date.strftime('%d %b %Y')} were already marked complete.")
    return redirect('planning:pending_assessments')


@login_required
@user_passes_test(is_coach, login_url='login')
def pending_assessments_view(request):
    coach_profile = None
    # Attempt to get coach_profile linked to the request.user
    # This logic seems a bit complex, ensure it correctly identifies the coach_profile for the logged-in user
    # A simpler way if request.user IS the coach user and has a OneToOne to Coach:
    # if hasattr(request.user, 'coach_profile'):
    # coach_profile = request.user.coach_profile
    # else:
    # messages.error(request, "Your user account is not linked to a Coach profile.")
    # return render(...)
    # For now, using your existing logic to find coach_profile:
    try:
        if hasattr(request.user, 'coach_profile') and request.user.coach_profile:
            coach_profile = request.user.coach_profile
        elif request.user.is_staff: # Assuming staff users are coaches
            coach_profile = Coach.objects.get(user=request.user)
        else:
            messages.error(request, "You do not have a coach profile.")
            return render(request, 'planning/pending_assessments.html', {'pending_items': [], 'page_title': "My Pending Assessments"})
    except Coach.DoesNotExist:
        messages.error(request, "Your coach profile could not be found.")
        return render(request, 'planning/pending_assessments.html', {'pending_items': [], 'page_title': "My Pending Assessments"})

    if not coach_profile: # Should be caught by above, but as a safeguard
        messages.error(request, "Coach profile not loaded or user is not a coach.")
        return render(request, 'planning/pending_assessments.html', {'pending_items': [], 'page_title': "My Pending Assessments"})

    date_limit_past = timezone.now().date() - timedelta(weeks=4) # Look back 4 weeks
    today = timezone.now().date()

    # Subquery to check if at least one player assessment was submitted by this coach for a session
    has_submitted_one_player_assessment_subquery = SessionAssessment.objects.filter(
        session=OuterRef('pk'),
        submitted_by=request.user
    )
    
    # Subquery to check if a group assessment was submitted by this coach for a session
    has_submitted_group_assessment_subquery = GroupAssessment.objects.filter(
        session=OuterRef('pk'),
        assessing_coach=request.user
    )

    # Get sessions attended by the coach within the date range that are not yet fully marked as complete for player assessments
    # AND do not have a group assessment by this coach yet.
    sessions_attended_by_coach = Session.objects.filter(
        coaches_attending=coach_profile,
        session_date__gte=date_limit_past,
        session_date__lte=today,
        is_cancelled=False # Exclude cancelled sessions
    ).annotate(
        # Check if player assessments are considered done by the coach for this session
        player_assessments_done_by_coach=Exists(
            CoachSessionCompletion.objects.filter(
                session=OuterRef('pk'),
                coach=coach_profile,
                assessments_submitted=True
            )
        ),
        # Check if a group assessment exists for this session by this coach
        group_assessment_submitted_by_coach=Exists(has_submitted_group_assessment_subquery),
        # Keep your existing logic for checking if at least one player assessment was made
        coach_has_submitted_one_player_assessment=Exists(has_submitted_one_player_assessment_subquery)
    ).select_related('school_group', 'venue').prefetch_related(
        'attendees',
        Prefetch('session_assessments', queryset=SessionAssessment.objects.filter(submitted_by=request.user), to_attr='assessments_by_this_coach')
    ).distinct().order_by('-session_date', '-session_start_time')

    pending_items_for_template = []
    for session in sessions_attended_by_coach:
        # Only consider sessions that have actually ended
        if session.end_datetime and session.end_datetime > timezone.now():
            continue

        # Player assessment logic (largely as before)
        players_in_session = list(session.attendees.all())
        assessed_player_ids_by_this_coach = {
            assessment.player_id for assessment in session.assessments_by_this_coach
        }
        players_to_assess_for_this_session = [
            player for player in players_in_session if player.id not in assessed_player_ids_by_this_coach
        ]
        
        # Determine if the "Mark Player Assessments Complete" button should show
        # This button should appear if there are players in the session AND
        # (either all players assigned to the coach are assessed OR at least one assessment has been made if list is long)
        # AND the coach hasn't already marked player assessments as complete for this session.
        coach_can_mark_player_assessments_complete = False
        if not session.player_assessments_done_by_coach and players_in_session:
            if not players_to_assess_for_this_session or session.coach_has_submitted_one_player_assessment:
                coach_can_mark_player_assessments_complete = True
        
        # If player assessments are not done OR group assessment is not done, then this session is "pending"
        if not session.player_assessments_done_by_coach or not session.group_assessment_submitted_by_coach:
            pending_items_for_template.append({
                'session': session,
                'players_to_assess': players_to_assess_for_this_session,
                'all_players_assessed_by_coach': not players_to_assess_for_this_session and players_in_session, # True if no players left to assess
                'coach_can_mark_player_assessments_complete': coach_can_mark_player_assessments_complete,
                'group_assessment_submitted': session.group_assessment_submitted_by_coach, # Pass this to the template
            })

    context = {
        'pending_items': pending_items_for_template,
        'page_title': "My Pending Assessments"
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
        'form': form, 'player': player, 
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
        'form': form, 'player': player, 
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
    except (json.JSONDecodeError, ValueError) as e: 
        return JsonResponse({'status': 'error', 'message': f'Invalid data: {e}'}, status=400)
    
    if not all([player_id, time_block_id, court_number_str]): 
        return JsonResponse({'status': 'error', 'message': 'Missing required data'}, status=400)
    
    try: 
        court_number = int(court_number_str)
        player = Player.objects.get(pk=player_id)
        time_block = TimeBlock.objects.get(pk=time_block_id)
    except (ObjectDoesNotExist, ValueError): 
        return JsonResponse({'status': 'error', 'message': 'Player, TimeBlock not found or invalid court number'}, status=404)
    
    if court_number > time_block.number_of_courts or court_number < 1: 
        return JsonResponse({'status': 'error', 'message': 'Invalid court number for this block'}, status=400)
    
    try: 
        assignment, created = ManualCourtAssignment.objects.update_or_create(
            time_block=time_block, player=player, defaults={'court_number': court_number}
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
    log_list = []
    if solosync_imported and SoloSessionLog is not None and hasattr(SoloSessionLog, 'objects'): 
        log_list = SoloSessionLog.objects.select_related('player', 'routine').order_by('-completed_at')
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
        'form': form, 'player': player, 
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
        'form': form, 'player': player, 
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
        'form': form, 'player': player, 
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
        'form': form, 'player': player, 
        'page_title': 'Add Match Result'
    }
    return render(request, 'planning/add_match_form.html', context)


@login_required
@user_passes_test(is_coach, login_url='login') 
def session_list(request):
    user = request.user
    sessions_queryset = Session.objects.select_related('school_group').prefetch_related('coaches_attending')
    if user.is_superuser: 
        sessions_list = sessions_queryset.order_by('-session_date', '-session_start_time')
        page_title = 'All Sessions'
    else:
        try:
            if hasattr(user, 'coach_profile') and user.coach_profile: 
                coach_profile = user.coach_profile
            else: 
                coach_profile = Coach.objects.get(user=user)
            sessions_list = sessions_queryset.filter(coaches_attending=coach_profile).order_by('-session_date', '-session_start_time')
            page_title = 'My Assigned Sessions'
        except (ObjectDoesNotExist, AttributeError): 
            messages.warning(request, "Your user account is not linked to a Coach profile.")
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
    session = get_object_or_404(
        Session.objects.prefetch_related(
            'attendees', 
            'coaches_attending'
        ).select_related('school_group'),
        pk=session_id
    )
    
    TimeBlockInlineFormSet = inlineformset_factory(
        Session, 
        TimeBlock, 
        # form=TimeBlockForm, # Uncomment if you have a custom TimeBlockForm
        fields=('start_offset_minutes', 'duration_minutes', 'number_of_courts', 'rotation_interval_minutes', 'block_focus'),
        extra=1, 
        can_delete=True 
    )

    timeblock_formset_instance = None # Initialize

    if request.method == 'POST':
        if 'update_attendance' in request.POST:
            attendance_form = AttendanceForm(request.POST, school_group=session.school_group)
            if attendance_form.is_valid():
                selected_players = attendance_form.cleaned_data['attendees']
                session.attendees.set(selected_players)
                ManualCourtAssignment.objects.filter(time_block__session=session).delete() 
                messages.success(request, "Attendance updated.")
                return redirect('planning:session_detail', session_id=session.id)
            else:
                # Need to initialize formset for re-render if attendance form is invalid
                timeblock_formset_instance = TimeBlockInlineFormSet(instance=session, prefix='timeblocks')
        
        elif 'update_timeblocks' in request.POST:
            timeblock_formset_instance = TimeBlockInlineFormSet(request.POST, instance=session, prefix='timeblocks')
            if timeblock_formset_instance.is_valid():
                timeblock_formset_instance.save()
                messages.success(request, "Time blocks updated successfully.")
                return redirect('planning:session_detail', session_id=session.id)
            else:
                # If timeblock formset is invalid, initialize attendance form for re-render
                current_attendees_for_form = session.attendees.all().order_by('last_name', 'first_name')
                initial_attendance = {'attendees': current_attendees_for_form}
                attendance_form = AttendanceForm(initial=initial_attendance, school_group=session.school_group)
        else: # Unrecognized POST, initialize both forms
            current_attendees_for_form = session.attendees.all().order_by('last_name', 'first_name')
            initial_attendance = {'attendees': current_attendees_for_form}
            attendance_form = AttendanceForm(initial=initial_attendance, school_group=session.school_group)
            timeblock_formset_instance = TimeBlockInlineFormSet(instance=session, prefix='timeblocks')

    else: # GET request
        current_attendees_for_form = session.attendees.all().order_by('last_name', 'first_name')
        initial_attendance = {'attendees': current_attendees_for_form}
        attendance_form = AttendanceForm(initial=initial_attendance, school_group=session.school_group)
        timeblock_formset_instance = TimeBlockInlineFormSet(instance=session, prefix='timeblocks')

    # --- MODIFIED: Prepare activities grouped by block AND court ---
    all_activities_for_session = ActivityAssignment.objects.filter(
        time_block__session=session
    ).select_related('drill', 'lead_coach').order_by(
        'time_block_id', 'court_number', 'order' # Ensure consistent ordering
    )
    
    activities_by_block_and_court = defaultdict(lambda: defaultdict(list))
    for activity in all_activities_for_session:
        activities_by_block_and_court[activity.time_block_id][activity.court_number].append(activity)
    # --- END MODIFICATION ---
    
    # Player grouping logic (uses saved time blocks)
    block_data = [] 
    # Iterate over actual saved time blocks for the player grouping display
    # This should use the instances from the database, not directly from the formset's forms before saving.
    saved_time_blocks = session.time_blocks.all().order_by('start_offset_minutes') # Query again or use formset.initial_forms
    
    display_attendees = session.attendees.all().order_by('last_name', 'first_name')
    if display_attendees.exists() and session.school_group:
        manual_assignments_all = ManualCourtAssignment.objects.filter(
            time_block__session=session, player__in=display_attendees
        ).select_related('player').values('time_block_id', 'player_id', 'court_number')
        
        manual_map = defaultdict(dict)
        for ma in manual_assignments_all: 
            manual_map[ma['time_block_id']][ma['player_id']] = ma['court_number']
        
        for block_instance in saved_time_blocks: # Iterate through actual saved blocks
            auto_assignments = _calculate_skill_priority_groups(display_attendees, block_instance.number_of_courts)
            block_manuals = manual_map.get(block_instance.id, {})
            manually_assigned_player_ids = set(block_manuals.keys())
            final_assignments = defaultdict(list)
            for court_num in range(1, block_instance.number_of_courts + 1): 
                final_assignments[court_num] = list(auto_assignments.get(court_num, []))
            for court_num in range(1, block_instance.number_of_courts + 1): 
                current_court_list = final_assignments[court_num]
                final_assignments[court_num] = [p for p in current_court_list if p.id not in manually_assigned_player_ids]
            for player_id, target_court in block_manuals.items():
                player_obj = next((p for p in display_attendees if p.id == player_id), None)
                if player_obj and player_obj not in final_assignments[target_court]: 
                    final_assignments[target_court].append(player_obj)
            for court_num in final_assignments: 
                final_assignments[court_num].sort(key=lambda p: (p.last_name, p.first_name))
            block_data.append({
                'block': block_instance, 
                'assignments': dict(final_assignments), 
                'has_manual': bool(block_manuals)
            })
            
    context = {
        'session': session, 
        'activities_by_block_and_court': dict(activities_by_block_and_court), # Pass new structure
        'attendance_form': attendance_form, 
        'current_attendees': display_attendees, 
        'block_data': block_data, 
        'timeblock_formset': timeblock_formset_instance, 
        'page_title': f"Session Plan: {session}"
    }
    return render(request, 'planning/session_detail.html', context)

@login_required
@user_passes_test(is_coach, login_url='login')
def visual_attendance_view(request, session_id):
    """
    Displays a mobile-first, visual list of players for a session
    to make taking attendance easier for coaches.
    """
    session = get_object_or_404(Session, pk=session_id)

    # Attendance cannot be taken if no group is assigned to the session
    if not session.school_group:
        messages.error(request, "Attendance cannot be managed because no school group is assigned to this session.")
        return redirect('planning:session_detail', session_id=session.id)

    # --- Handle form submission ---
    if request.method == 'POST':
        # Get the list of player IDs that were checked in the form
        attendee_ids = request.POST.getlist('attendees')

        # Efficiently update the session's attendees
        session.attendees.set(attendee_ids)

        messages.success(request, f"Attendance for {session.school_group.name} has been updated successfully.")
        return redirect('planning:session_detail', session_id=session.id)

    # --- Prepare data for displaying the page ---
    # Get all active players that belong to this session's group
    all_players_in_group = session.school_group.players.filter(is_active=True).order_by('first_name', 'last_name')
    
    # Get a set of IDs for players who are currently marked as attending for quick lookups
    current_attendee_ids = set(session.attendees.values_list('id', flat=True))
    
    # Create a list of players, annotating each with their attendance status
    player_list_with_status = []
    for player in all_players_in_group:
        player_list_with_status.append({
            'player': player,
            'is_attending': player.id in current_attendee_ids
        })

    context = {
        'session': session,
        'school_group': session.school_group,
        'player_list': player_list_with_status,
        'page_title': f"Update Attendance: {session.school_group.name}"
    }
    
    # We will create this new template in the next step
    return render(request, 'planning/visual_attendance.html', context)

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
        'players': players, 'groups': groups, 
        'selected_group_id': selected_group_id, 
        'search_query': search_query, 'page_title': page_title
    }
    return render(request, 'planning/players_list.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def one_page_plan_view(request, session_id):
    session = get_object_or_404(
        Session.objects.select_related('school_group').prefetch_related('coaches_attending'), 
        pk=session_id
    )
    time_blocks = session.time_blocks.order_by('start_offset_minutes')
    activities = ActivityAssignment.objects.filter(
        time_block__session=session
    ).select_related('drill', 'lead_coach').order_by(
        'time_block__start_offset_minutes', 'court_number', 'order'
    )
    coaches = session.coaches_attending.all()
    context = {
        'session': session, 'time_blocks': time_blocks, 
        'activities': activities, 'coaches': coaches
    }
    return render(request, 'planning/one_page_plan.html', context)


@login_required
@user_passes_test(is_coach, login_url='login') 
def session_calendar_view(request):
    current_django_tz = timezone.get_current_timezone()
    user = request.user
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
        if not (1 <= month <= 12): 
            month = timezone.now().month 
        current_date_for_nav = date_obj(year, month, 1) 
    except (ValueError, TypeError):
        now_in_current_tz = timezone.now()
        year = now_in_current_tz.year
        month = now_in_current_tz.month
        current_date_for_nav = date_obj(year, month, 1) 
    
    prev_month_date = current_date_for_nav - timedelta(days=1)
    prev_month_date = prev_month_date.replace(day=1)   
    if current_date_for_nav.month == 12: 
        next_month_date = date_obj(current_date_for_nav.year + 1, 1, 1) 
    else: 
        next_month_date = date_obj(current_date_for_nav.year, current_date_for_nav.month + 1, 1) 
    
    sessions_base_qs = Session.objects.filter(
        session_date__year=year, session_date__month=month
    ).select_related('school_group').prefetch_related('coaches_attending', 'attendees')
    
    if user.is_superuser: 
        sessions_for_month = sessions_base_qs.order_by('session_date', 'session_start_time')
    elif hasattr(user, 'coach_profile') and user.coach_profile: 
        coach_profile = user.coach_profile
        sessions_for_month = sessions_base_qs.filter(coaches_attending=coach_profile).order_by('session_date', 'session_start_time')
    else:
        try: 
            coach_profile = Coach.objects.get(user=user)
            sessions_for_month = sessions_base_qs.filter(coaches_attending=coach_profile).order_by('session_date', 'session_start_time')
        except Coach.DoesNotExist: 
            sessions_for_month = Session.objects.none()
            if not user.is_superuser : 
                messages.warning(request, "Your user account is not linked to a Coach profile.")
                
    PREDEFINED_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5', '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5']
    school_group_colors = {}
    color_index = 0
    unique_school_groups_in_month = SchoolGroup.objects.filter(sessions__in=sessions_for_month).distinct()
    for sg in unique_school_groups_in_month:
        if sg.id not in school_group_colors: 
            school_group_colors[sg.id] = PREDEFINED_COLORS[color_index % len(PREDEFINED_COLORS)]
            color_index += 1
            
    calendar_events = []
    for session in sessions_for_month:
        s_start_time = session.session_start_time if session.session_start_time else time.min
        naive_start_datetime = dt_class.combine(session.session_date, s_start_time)
        start_datetime_aware = naive_start_datetime.replace(tzinfo=current_django_tz)
        end_datetime_aware = start_datetime_aware + timedelta(minutes=session.planned_duration_minutes)
        coaches_list = [coach.name for coach in session.coaches_attending.all()]
        if not coaches_list and hasattr(session, 'get_assigned_coaches_display'): 
            coaches_list = [session.get_assigned_coaches_display()]
        time_str_display = s_start_time.strftime('%H:%M')
        school_group_name = session.school_group.name if session.school_group else "No Group"
        event_title = f"{time_str_display} - {school_group_name}"
        event_custom_color = school_group_colors.get(session.school_group_id) if session.school_group else None 
        final_event_color = '#d3d3d3' if session.is_cancelled else event_custom_color
        final_text_color = '#a9a9a9' if session.is_cancelled else ('#FFFFFF' if event_custom_color else None)
        calendar_events.append({
            'id': session.pk, 'title': event_title, 
            'start': start_datetime_aware.isoformat(), 'end': end_datetime_aware.isoformat(), 
            'allDay': False, 'color': final_event_color, 'textColor': final_text_color, 
            'borderColor': final_event_color, 
            'extendedProps': {
                'school_group_name': school_group_name, 
                'session_time_str': f"{s_start_time.strftime('%H:%M')} - {end_datetime_aware.strftime('%H:%M')}", 
                'venue_name': getattr(session, 'venue_name', session.venue.name if session.venue else "N/A"), # Corrected venue access
                'coaches_attending': coaches_list, 
                'attendees_count': session.attendees.count(), 
                'duration_minutes': session.planned_duration_minutes, 
                'is_cancelled_bool': session.is_cancelled, 
                'status_display': "Cancelled" if session.is_cancelled else "Scheduled", 
                'notes': session.notes if session.notes else "", 
                'admin_url': reverse('admin:planning_session_change', args=[session.pk]) if request.user.is_superuser else None, 
                'session_planner_url': reverse('planning:session_detail', args=[session.pk]), 
                'event_custom_color': final_event_color
            }
        })
        
    context = {
        'calendar_events_json': json.dumps(calendar_events), 
        'current_year': year, 'current_month': month, 
        'current_month_display': current_date_for_nav.strftime('%B %Y'), 
        'prev_year': prev_month_date.year, 'prev_month': prev_month_date.month, 
        'next_year': next_month_date.year, 'next_month': next_month_date.month, 
        'page_title': 'Session Calendar', 
        'is_staff_user': request.user.is_staff
    }
    return render(request, 'planning/session_calendar.html', context)

@login_required
@user_passes_test(is_coach, login_url='login')
@login_required
def export_sessions_ics_view(request):
    """
    Generates and serves an iCalendar (.ics) file for a coach's or all sessions
    in a given month and year.
    """
    user = request.user
    now = timezone.now()
    try:
        year = int(request.GET.get('year', now.year))
        month = int(request.GET.get('month', now.month))
    except (ValueError, TypeError):
        year = now.year
        month = now.month

    sessions_qs = Session.objects.none()

    if user.is_superuser:
        sessions_qs = Session.objects.filter(
            session_date__year=year, 
            session_date__month=month,
            is_cancelled=False
        )
    else:
        try:
            # It's better to get the Coach profile via the user object
            coach_profile = Coach.objects.get(user=request.user)
            sessions_qs = Session.objects.filter(
                coaches_attending=coach_profile,
                session_date__year=year,
                session_date__month=month,
                is_cancelled=False
            )
        except Coach.DoesNotExist:
            messages.error(request, "Your user account is not linked to a Coach profile.")
            return redirect('planning:session_calendar')
    
    # Eager load related data for efficiency
    sessions_qs = sessions_qs.select_related('school_group', 'venue').prefetch_related('coaches_attending')

    cal = Calendar()
    for session in sessions_qs:
        # Skip if crucial date/time info is missing
        if not (session.session_date and session.session_start_time):
            continue

        start_datetime = timezone.make_aware(
            dt_class.combine(session.session_date, session.session_start_time)
        )
        end_datetime = start_datetime + timedelta(minutes=session.planned_duration_minutes)
        
        coaches_str = ", ".join([coach.name for coach in session.coaches_attending.all()])
        
        e = Event()
        e.name = f"{session.school_group.name if session.school_group else 'Session'}"
        e.begin = start_datetime
        e.end = end_datetime
        e.description = f"Coaches: {coaches_str}\nNotes: {session.notes}"
        if session.venue:
            e.location = session.venue.name

        # --- CORRECTED ATTENDEE LOGIC ---
        # Create a list of Attendee objects only from saved Coach instances with an email
        attendees = []
        for coach in session.coaches_attending.all():
            # This check prevents the "unhashable" error by ensuring the coach object is valid
            if coach.pk and coach.email:
                attendees.append(Attendee(f"mailto:{coach.email}", common_name=coach.name))
        
        # The ics library handles making this a set internally if needed
        e.attendees = attendees
        # --- END CORRECTION ---

        cal.events.add(e)

    response = HttpResponse(str(cal), content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="squashsync_sessions_{year}_{month:02d}.ics"'
    return response

@login_required
@user_passes_test(is_coach, login_url='login')
@login_required
def export_monthly_schedule_csv(request):
    """
    Generates and serves a CSV file of all sessions for a given month and year.
    """
    try:
        year = int(request.GET.get('year'))
        month = int(request.GET.get('month'))
    except (ValueError, TypeError):
        return HttpResponse("Invalid year or month provided.", status=400)

    start_date, end_date = get_month_start_end(year, month)
    
    sessions_for_month = Session.objects.filter(
        session_date__gte=start_date,
        session_date__lte=end_date
    ).select_related('school_group', 'venue').prefetch_related('coaches_attending').order_by('session_date', 'session_start_time')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sessions_{year}_{month:02d}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Day', 'Time Slot', 'Group', 'Coaches', 'Venue', 'Status'])

    for session in sessions_for_month:
        start_time = session.session_start_time.strftime('%H:%M')
        end_time = (session.start_datetime + timedelta(minutes=session.planned_duration_minutes)).strftime('%H:%M')
        time_slot = f"{start_time} - {end_time}"
        coaches_str = ", ".join([coach.name for coach in session.coaches_attending.all()]) or "N/A"
        
        writer.writerow([
            session.session_date,
            session.session_date.strftime('%A'),
            time_slot,
            session.school_group.name if session.school_group else "N/A",
            coaches_str,
            session.venue.name if session.venue else "N/A",
            "Cancelled" if session.is_cancelled else "Scheduled"
        ])

    return response


@login_required
@user_passes_test(is_superuser, login_url='login') 
@require_POST 
def toggle_assessment_visibility(request, assessment_id):
    assessment = get_object_or_404(SessionAssessment, pk=assessment_id)
    assessment.is_hidden = not assessment.is_hidden
    assessment.save()
    if assessment.is_hidden: 
        messages.success(request, f"Assessment for {assessment.player.full_name} on {assessment.session.session_date.strftime('%Y-%m-%d')} is now hidden.")
    else: 
        messages.success(request, f"Assessment for {assessment.player.full_name} on {assessment.session.session_date.strftime('%Y-%m-%d')} is now visible.")
    return redirect('planning:player_profile', player_id=assessment.player.id)


@login_required
@user_passes_test(is_superuser, login_url='login') 
@require_POST 
def toggle_assessment_superuser_review_status(request, assessment_id):
    assessment = get_object_or_404(SessionAssessment, pk=assessment_id)
    if not assessment.superuser_reviewed: 
        assessment.superuser_reviewed = True
        assessment.save()
        messages.success(request, f"Assessment for {assessment.player.full_name} (Session: {assessment.session.session_date.strftime('%d %b %Y')}) marked as reviewed.")
    else: 
        messages.info(request, f"Assessment for {assessment.player.full_name} was already marked as reviewed.")
    return redirect('planning:homepage') 


@login_required
def confirm_session_attendance(request, session_id, token):
    payload_str = verify_confirmation_token(token)
    if not payload_str: 
        messages.error(request, "Invalid or expired confirmation link.")
        return redirect('planning:homepage')
    try: 
        token_coach_id_str, token_session_id_str = payload_str.split(':')
        token_coach_id = int(token_coach_id_str)
        token_session_id = int(token_session_id_str)
    except ValueError: 
        messages.error(request, "Malformed confirmation link.")
        return redirect('planning:homepage')
    if request.user.id != token_coach_id: 
        messages.error(request, "This confirmation link is not valid for your account.")
        return redirect('planning:homepage') 
    if session_id != token_session_id: 
        messages.error(request, "Session mismatch in confirmation link.")
        return redirect('planning:homepage')
    
    session_obj = get_object_or_404(Session, pk=session_id)
    try:
        availability, created = CoachAvailability.objects.update_or_create(
            coach=request.user, 
            session=session_obj, 
            defaults={
                'is_available': True, 
                'notes': 'Confirmed via email link.', 
                'last_action': 'CONFIRM', 
                'status_updated_at': timezone.now()
            }
        ) 
        if not created and not availability.is_available: 
            availability.is_available = True
            availability.notes = 'Re-confirmed via email link.'
            availability.last_action = 'CONFIRM'
            availability.status_updated_at = timezone.now()
            availability.save()
        messages.success(request, f"Thank you for confirming your attendance for session: {session_obj} on {session_obj.session_date.strftime('%d %b %Y')}.")
    except Exception as e: 
        messages.error(request, f"An error occurred while confirming your attendance: {e}")
        return redirect('planning:homepage') 
    
    return render(request, 'planning/confirmation_response.html', {
        'page_title': "Attendance Confirmed", 
        'message_title': "Attendance Confirmed!", 
        'message_body': f"Your attendance for the session '{session_obj}' on {session_obj.session_date.strftime('%A, %d %B %Y')} at {session_obj.session_start_time.strftime('%H:%M')} has been confirmed."
    })


@login_required
def decline_session_attendance(request, session_id, token):
    payload_str = verify_confirmation_token(token)
    if not payload_str: 
        messages.error(request, "Invalid or expired decline link.")
        return redirect('planning:homepage')
    try: 
        token_coach_id_str, token_session_id_str = payload_str.split(':')
        token_coach_id = int(token_coach_id_str)
        token_session_id = int(token_session_id_str)
    except ValueError: 
        messages.error(request, "Malformed decline link.")
        return redirect('planning:homepage')
    if request.user.id != token_coach_id: 
        messages.error(request, "This decline link is not valid for your account.")
        return redirect('planning:homepage')
    if session_id != token_session_id: 
        messages.error(request, "Session mismatch in decline link.")
        return redirect('planning:homepage')
    
    session_obj = get_object_or_404(Session, pk=session_id)
    current_coach_profile = None 
    try:
        if hasattr(request.user, 'coach_profile') and request.user.coach_profile: 
            current_coach_profile = request.user.coach_profile
        else: 
            current_coach_profile = Coach.objects.filter(user=request.user).first()
    except Coach.DoesNotExist: 
        pass

    if request.method == 'POST':
        reason = request.POST.get('reason', 'Declined via email link.')
        notes_to_save = f"Declined via email link. Reason: {reason}" if reason.strip() else "Declined via email link." 
        
        availability, created = CoachAvailability.objects.update_or_create(
            coach=request.user, 
            session=session_obj, 
            defaults={
                'is_available': False, 
                'notes': notes_to_save, 
                'last_action': 'DECLINE', 
                'status_updated_at': timezone.now()
            }
        ) 
        if not created and availability.is_available: 
            availability.is_available = False
            availability.notes = notes_to_save
            availability.last_action = 'DECLINE'
            availability.status_updated_at = timezone.now()
            availability.save()
        messages.info(request, f"Your attendance for session: {session_obj} on {session_obj.session_date.strftime('%d %b %Y')} has been marked as unavailable.")
        
        if current_coach_profile and current_coach_profile in session_obj.coaches_attending.all():
            session_obj.coaches_attending.remove(current_coach_profile)
            messages.info(request, f"You have been removed from assigned coaches for this session.")
            print(f"SUPERUSER NOTIFICATION: Coach {current_coach_profile.name} declined session {session_obj.id} after email link.")

        return render(request, 'planning/confirmation_response.html', {
            'page_title': "Attendance Declined", 
            'message_title': "Attendance Declined", 
            'message_body': f"You have declined attendance for the session '{session_obj}' on {session_obj.session_date.strftime('%A, %d %B %Y')}."
        })
    return render(request, 'planning/decline_attendance_form.html', {
        'page_title': "Decline Attendance", 
        'session': session_obj, 
        'token': token
    })


@login_required
@user_passes_test(is_coach, login_url='login') 
@require_POST 
def direct_confirm_attendance(request, session_id):
    session_obj = get_object_or_404(Session, pk=session_id)
    coach_user = request.user
    try:
        availability, created = CoachAvailability.objects.update_or_create(
            coach=coach_user, 
            session=session_obj, 
            defaults={
                'is_available': True, 
                'notes': 'Confirmed via dashboard.', 
                'last_action': 'CONFIRM', 
                'status_updated_at': timezone.now()
            }
        ) 
        if not created and not availability.is_available: 
            availability.is_available = True
            availability.notes = 'Re-confirmed via dashboard.'
            availability.last_action = 'CONFIRM'
            availability.status_updated_at = timezone.now()
            availability.save()
        messages.success(request, f"Attendance confirmed for session: {session_obj} on {session_obj.session_date.strftime('%d %b %Y')}.")
    except Exception as e: 
        messages.error(request, f"An error occurred: {e}")
    return redirect('planning:homepage')


@login_required
@user_passes_test(is_coach, login_url='login')
@require_POST
def direct_decline_attendance(request, session_id):
    session_obj = get_object_or_404(Session, pk=session_id)
    coach_user = request.user
    current_coach_profile = None
    try:
        if hasattr(request.user, 'coach_profile') and request.user.coach_profile: 
            current_coach_profile = request.user.coach_profile
        else: 
            current_coach_profile = Coach.objects.filter(user=request.user).first()
    except Coach.DoesNotExist: 
        pass
    
    notes_from_form = request.POST.get('decline_notes', 'Declined via dashboard.') 
    try:
        availability, created = CoachAvailability.objects.update_or_create(
            coach=coach_user, 
            session=session_obj, 
            defaults={
                'is_available': False, 
                'notes': notes_from_form, 
                'last_action': 'DECLINE', 
                'status_updated_at': timezone.now()
            }
        ) 
        if not created and availability.is_available: 
            availability.is_available = False
            availability.notes = notes_from_form
            availability.last_action = 'DECLINE'
            availability.status_updated_at = timezone.now()
            availability.save()
        messages.info(request, f"Attendance declined for session: {session_obj} on {session_obj.session_date.strftime('%d %b %Y')}.")
        if current_coach_profile and current_coach_profile in session_obj.coaches_attending.all():
            session_obj.coaches_attending.remove(current_coach_profile)
            messages.info(request, f"You have been removed from assigned coaches for this session.")
            print(f"SUPERUSER NOTIFICATION: Coach {current_coach_profile.name} declined session {session_obj.id} from dashboard.")
    except Exception as e: 
        messages.error(request, f"An error occurred: {e}")
    return redirect('planning:homepage')


@login_required
# @user_passes_test(is_coach, login_url='login') # Make sure your permission check is correct
def set_bulk_availability_view(request):
    """
    Allows a logged-in coach to set their general availability for all
    sessions generated from recurring rules within a selected month and year.
    This does NOT assign them to the session, it only records their availability.
    """
    try:
        coach_profile = Coach.objects.get(user=request.user)
    except Coach.DoesNotExist:
        messages.error(request, "Your user account is not linked to a Coach profile.")
        return redirect('homepage')

    if request.method == 'POST':
        selected_month = int(request.POST.get('month'))
        selected_year = int(request.POST.get('year'))
        start_date, end_date = get_month_start_end(selected_year, selected_month)
        
        rules = ScheduledClass.objects.filter(is_active=True)
        
        availability_updated_count = 0

        for rule in rules:
            availability_key = f'availability_rule_{rule.id}'
            availability_status_str = request.POST.get(availability_key)

            if not availability_status_str or availability_status_str == 'NO_CHANGE':
                continue

            is_available = None
            notes = ""
            if availability_status_str == 'AVAILABLE':
                is_available = True
            elif availability_status_str == 'UNAVAILABLE':
                is_available = False
            elif availability_status_str == 'EMERGENCY':
                is_available = True # Mark as available
                notes = "Emergency only" # Add a note to signify emergency status

            sessions_to_update = Session.objects.filter(
                generated_from_rule=rule,
                session_date__gte=start_date,
                session_date__lte=end_date,
                is_cancelled=False
            )
            
            for session in sessions_to_update:
                CoachAvailability.objects.update_or_create(
                    coach=request.user,
                    session=session,
                    defaults={
                        'is_available': is_available,
                        'notes': notes,
                        'status_updated_at': timezone.now()
                    }
                )
                availability_updated_count += 1
        
        month_name = calendar.month_name[selected_month]
        messages.success(request, f"Your availability preference for {availability_updated_count} potential sessions in {month_name} {selected_year} has been recorded.")
        return redirect(f"{reverse('planning:set_bulk_availability')}?year={selected_year}&month={selected_month}")

    # --- GET request handling ---
    now = timezone.now()
    default_year = now.year
    default_month = now.month

    selected_year = int(request.GET.get('year', default_year))
    selected_month = int(request.GET.get('month', default_month))

    month_year_form = MonthYearSelectionForm(initial={'month': selected_month, 'year': selected_year})
    
    # Fetch all active scheduled classes
    scheduled_classes_qs = ScheduledClass.objects.filter(is_active=True).select_related('school_group', 'default_venue').order_by('day_of_week', 'start_time')

    # Get the coach's current availability for these rules in the selected month
    # This is complex because availability is per-session, not per-rule.
    # We will handle the initial state in the template for simplicity for now.
    
    # Group scheduled classes by day of the week
    grouped_classes = {
        'Monday': [], 'Tuesday': [], 'Wednesday': [], 'Thursday': [], 'Friday': [], 'Saturday': [], 'Sunday': []
    }
    for rule in scheduled_classes_qs:
        day_name = rule.get_day_of_week_display()
        if day_name in grouped_classes:
            grouped_classes[day_name].append(rule)

    context = {
        'page_title': "Set Bulk Availability",
        'month_year_form': month_year_form,
        'grouped_classes': grouped_classes, # Pass the grouped data
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_month_display': calendar.month_name[selected_month],
    }
    return render(request, 'planning/set_bulk_availability.html', context)

@login_required
@user_passes_test(is_coach, login_url='login')
def add_edit_group_assessment(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    
    # Permission check: Only allow coaches assigned to this session to assess
    # or superusers.
    is_assigned_coach = session.coaches_attending.filter(user=request.user).exists()
    if not (request.user.is_superuser or is_assigned_coach):
        messages.error(request, "You are not authorized to assess this session's group.")
        return redirect('planning:pending_assessments') # Or another appropriate redirect

    # Check if an assessment already exists for this coach and session
    try:
        group_assessment = GroupAssessment.objects.get(session=session, assessing_coach=request.user)
    except GroupAssessment.DoesNotExist:
        group_assessment = None # No existing assessment, so we'll create one

    if request.method == 'POST':
        form = GroupAssessmentForm(request.POST, instance=group_assessment)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.session = session
            assessment.assessing_coach = request.user
            # assessment_datetime is auto_now_add or default, so no need to set manually unless editing
            if group_assessment: # If editing, ensure datetime is not re-set by default
                assessment.assessment_datetime = group_assessment.assessment_datetime 
            assessment.save()
            messages.success(request, f"Group assessment for {session.school_group.name} on {session.session_date} has been saved.")
            return redirect('planning:pending_assessments') # Redirect to pending assessments or session detail
    else:
        form = GroupAssessmentForm(instance=group_assessment)

    context = {
        'form': form,
        'session': session,
        'school_group': session.school_group, # Get school_group from the session
        'page_title': f"Assess Group: {session.school_group.name} - {session.session_date}",
        'group_assessment_instance': group_assessment # Pass instance to template for "Edit" context
    }
    return render(request, 'planning/add_edit_group_assessment.html', context)


@login_required
@user_passes_test(is_coach, login_url='login')
def school_group_list(request):
    # Add any filtering or search logic here if needed in the future
    school_groups = SchoolGroup.objects.all().order_by('name')
    context = {
        'school_groups': school_groups,
        'page_title': "School Groups"
    }
    return render(request, 'planning/school_group_list.html', context)


@login_required
# @user_passes_test(is_coach, login_url='login') # Or your preferred permission check
def school_group_profile(request, group_id):
    school_group = get_object_or_404(SchoolGroup, pk=group_id)
    
    group_assessments = GroupAssessment.objects.filter(
        session__school_group=school_group
    ).select_related(
        'assessing_coach', 'session', 'session__venue'
    ).order_by('-assessment_datetime')

    players_in_group = school_group.players.filter(is_active=True).order_by('last_name', 'first_name')

    # --- Attendance Period Filter ---
    # Default date range: last 90 days
    default_end_date = timezone.now().date()
    default_start_date = default_end_date - timedelta(days=89) # Approx 3 months

    # Initialize form with GET data or defaults
    filter_form = AttendancePeriodFilterForm(request.GET or None, initial={
        'start_date': default_start_date.strftime('%Y-%m-%d'),
        'end_date': default_end_date.strftime('%Y-%m-%d')
    })

    start_date_filter = default_start_date
    end_date_filter = default_end_date

    if filter_form.is_valid() and request.GET: # Process if form submitted and valid
        sd = filter_form.cleaned_data.get('start_date')
        ed = filter_form.cleaned_data.get('end_date')
        if sd:
            start_date_filter = sd
        if ed:
            end_date_filter = ed
    elif not request.GET: # If no GET params, ensure form still uses defaults for display
        filter_form = AttendancePeriodFilterForm(initial={
            'start_date': default_start_date.strftime('%Y-%m-%d'),
            'end_date': default_end_date.strftime('%Y-%m-%d')
        })


    # --- Attendance Calculations ---
    group_average_attendance = 0
    player_attendance_in_group = []
    
    # Get all relevant past/current sessions for this group within the filtered period
    relevant_sessions = Session.objects.filter(
        school_group=school_group,
        session_date__gte=start_date_filter,
        session_date__lte=end_date_filter, # Ensure we only count sessions up to 'today' or selected end date
        is_cancelled=False
    ).prefetch_related('attendees') # Prefetch attendees for efficiency

    total_session_percentage_sum = 0
    sessions_counted_for_group_average = 0

    # V1 Assumption: For group average, "expected" attendees for a session are current members of the group.
    # This doesn't perfectly account for players joining/leaving the group over the period.
    current_group_member_count = players_in_group.count()

    if current_group_member_count > 0 and relevant_sessions.exists():
        for session in relevant_sessions:
            # Ensure session has actually passed or is today (and ended) to be counted for attendance
            if session.end_datetime and session.end_datetime > timezone.now():
                continue # Skip future sessions

            actual_attendees_count = session.attendees.count()
            # We use current_group_member_count as the 'expected' for V1 simplicity.
            # A more accurate historical 'expected' would require tracking player-group membership over time.
            if current_group_member_count > 0: # Avoid division by zero
                session_attendance_percentage = (actual_attendees_count / current_group_member_count) * 100
                total_session_percentage_sum += session_attendance_percentage
                sessions_counted_for_group_average += 1
        
        if sessions_counted_for_group_average > 0:
            group_average_attendance = total_session_percentage_sum / sessions_counted_for_group_average

    # Individual Player Attendance for this Group's Sessions
    for player in players_in_group:
        sessions_player_attended_for_this_group = 0
        # "Expected" sessions for this player within this group's schedule for the period
        # V1 Assumption: If a player is currently in the group, they were "expected" at all group sessions
        # during the filtered period. This doesn't account for when they joined/left the group.
        total_group_sessions_in_period_for_player = 0

        for session in relevant_sessions:
             # Ensure session has actually passed or is today (and ended)
            if session.end_datetime and session.end_datetime > timezone.now():
                continue
            
            total_group_sessions_in_period_for_player +=1 # Counted as an expected session for current members

            if player in session.attendees.all():
                sessions_player_attended_for_this_group += 1
        
        player_group_attendance_percentage = 0
        if total_group_sessions_in_period_for_player > 0:
            player_group_attendance_percentage = (sessions_player_attended_for_this_group / total_group_sessions_in_period_for_player) * 100
        
        player_attendance_in_group.append({
            'player': player,
            'attended_sessions': sessions_player_attended_for_this_group,
            'total_group_sessions': total_group_sessions_in_period_for_player,
            'percentage': player_group_attendance_percentage
        })

    context = {
        'school_group': school_group,
        'players_in_group': players_in_group,
        'group_assessments': group_assessments,
        'filter_form': filter_form, # Add form to context
        'start_date_filter': start_date_filter, # Pass current filter dates for display
        'end_date_filter': end_date_filter,     # Pass current filter dates for display
        'group_average_attendance': group_average_attendance,
        'player_attendance_in_group': player_attendance_in_group,
        'page_title': f"Profile: {school_group.name}"
    }
    return render(request, 'planning/school_group_profile.html', context)
# --- End GroupAssessment Views ---

@require_POST # This view should only accept POST requests
@user_passes_test(lambda u: u.is_superuser) # Only superusers can access this
def toggle_group_assessment_superuser_review_status(request, group_assessment_id):
    assessment = get_object_or_404(GroupAssessment, pk=group_assessment_id)
    
    # Toggle the status
    assessment.superuser_reviewed = not assessment.superuser_reviewed
    assessment.save(update_fields=['superuser_reviewed'])
    
    if assessment.superuser_reviewed:
        messages.success(request, f"Group assessment for session '{assessment.session}' marked as reviewed.")
    else:
        messages.info(request, f"Group assessment for session '{assessment.session}' marked as unreviewed.")
        
    # Redirect back to the admin homepage (or wherever is appropriate)
    # Using a query parameter to attempt to return to the same part of the page is complex
    # and usually handled by frontend JS or just redirecting to the top of the dashboard.
    return redirect(request.META.get('HTTP_REFERER', reverse('homepage')))

@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='homepage') # Only superusers can view the coach list
def coach_list_view(request):
    """
    Displays a list of all active coaches for superuser administration.
    """
    coaches = Coach.objects.filter(is_active=True).select_related('user').order_by('name') # Or 'user__last_name', 'user__first_name'
    context = {
        'coaches': coaches,
        'page_title': "Coach Profiles"
    }
    return render(request, 'planning/coach_list.html', context)

@login_required
def coach_profile_view(request, coach_id=None):
    target_coach_user = None # User instance of the target coach
    target_coach_profile = None # Coach model instance
    viewing_own_profile = False

    if coach_id:
        if not request.user.is_superuser:
            messages.error(request, "You are not authorized to view this coach's profile.")
            return redirect('homepage')
        target_coach_profile = get_object_or_404(Coach, pk=coach_id)
        if not target_coach_profile.user: # Ensure coach profile is linked to a user
            messages.error(request, "This coach profile is not linked to an active user account.")
            return redirect('planning:coach_list') # Or appropriate error page
        target_coach_user = target_coach_profile.user
    elif request.user.is_staff:
        try:
            if hasattr(request.user, 'coach_profile') and request.user.coach_profile:
                target_coach_profile = request.user.coach_profile
            else:
                target_coach_profile = Coach.objects.get(user=request.user)
            target_coach_user = request.user # The logged-in user is the target coach user
            viewing_own_profile = True
        except Coach.DoesNotExist:
            messages.error(request, "Your coach profile could not be found.")
            return redirect('homepage')
    else:
        messages.error(request, "You are not authorized to view this page.")
        return redirect('homepage')

    if not target_coach_profile or not target_coach_user:
        messages.error(request, "Could not load the coach profile.")
        return redirect('homepage')

    # --- Availability Summary Calculation ---
    now_for_defaults = timezone.now()
    default_filter_year = now_for_defaults.year
    default_filter_month = now_for_defaults.month

    # Handle submitted filter form or use defaults
    if request.GET.get('month') and request.GET.get('year'):
        availability_filter_form = MonthYearFilterForm(request.GET)
        if availability_filter_form.is_valid():
            selected_month = int(availability_filter_form.cleaned_data['month'])
            selected_year = int(availability_filter_form.cleaned_data['year'])
        else: # Form invalid, fall back to defaults
            selected_month = default_filter_month
            selected_year = default_filter_year
            # Re-initialize form with defaults if GET params were bad but form submitted
            availability_filter_form = MonthYearFilterForm(initial={'month': default_filter_month, 'year': default_filter_year})
    else: # Initial load or no filter params
        selected_month = default_filter_month
        selected_year = default_filter_year
        availability_filter_form = MonthYearFilterForm(initial={'month': default_filter_month, 'year': default_filter_year})

    # Get start and end dates for the selected month/year
    filter_start_date, filter_end_date = get_month_start_end(selected_year, selected_month)

    # Denominator: All non-cancelled sessions in the system for the selected month
    total_possible_sessions_in_month = Session.objects.filter(
        session_date__gte=filter_start_date,
        session_date__lte=filter_end_date,
        is_cancelled=False
    ).count()

    # Numerator: Distinct sessions the target_coach_user marked as available for in that month
    sessions_coach_available_for = CoachAvailability.objects.filter(
        coach=target_coach_user, # Link to the User model instance
        is_available=True,
        session__session_date__gte=filter_start_date,
        session__session_date__lte=filter_end_date,
        session__is_cancelled=False
    ).values_list('session_id', flat=True).distinct().count()
    
    availability_percentage = 0
    if total_possible_sessions_in_month > 0:
        availability_percentage = (sessions_coach_available_for / total_possible_sessions_in_month) * 100
    
    availability_summary_calculated = {
        'selected_month_name': calendar.month_name[selected_month],
        'selected_year': selected_year,
        'total_possible_sessions': total_possible_sessions_in_month,
        'sessions_coach_available_for': sessions_coach_available_for,
        'percentage': availability_percentage
    }
    # --- End Availability Summary Calculation ---

    # Fetch other data for the profile (sessions attended, assessments, events, hours coached)
    # (Using the logic from our previous step for these)
    sessions_attended = Session.objects.filter(coaches_attending=target_coach_profile, session_date__lte=timezone.now().date()).order_by('-session_date', '-session_start_time')
    player_assessments_made = SessionAssessment.objects.filter(submitted_by=target_coach_user).select_related('player', 'session', 'session__school_group').order_by('-date_recorded')
    group_assessments_made = GroupAssessment.objects.filter(assessing_coach=target_coach_user).select_related('session', 'session__school_group').order_by('-assessment_datetime')
    events_attended = Event.objects.filter(attending_coaches=target_coach_profile).order_by('-event_date')
    
    total_minutes_coached = 0
    for session in sessions_attended.filter(is_cancelled=False): # Only count non-cancelled
        total_minutes_coached += session.planned_duration_minutes
    total_hours_coached = total_minutes_coached / 60 if total_minutes_coached > 0 else 0

    context = {
        'target_coach': target_coach_profile,
        'viewing_own_profile': viewing_own_profile,
        'sessions_attended': sessions_attended,
        'player_assessments_made': player_assessments_made,
        'group_assessments_made': group_assessments_made,
        'events_attended': events_attended,
        'availability_filter_form': availability_filter_form, # Add form to context
        'availability_summary': availability_summary_calculated, # Use the new calculated summary
        'total_hours_coached': total_hours_coached,
        'page_title': f"Coach Profile: {target_coach_profile.name or target_coach_user.username}"
    }
    return render(request, 'planning/coach_profile.html', context)

