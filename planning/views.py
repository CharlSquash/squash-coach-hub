# planning/views.py
import json
import datetime
from datetime import timedelta, time # Import time specifically if needed elsewhere
from collections import defaultdict

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q, Prefetch, Count # Removed FieldError from here
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.core.exceptions import FieldError # *** CORRECTED IMPORT LOCATION ***

# Import models from the planning app
from .models import (
    Session, SchoolGroup, Player, Coach, Drill, TimeBlock,
    ActivityAssignment, SessionAssessment, CourtSprintRecord,
    VolleyRecord, BackwallDriveRecord, MatchResult,
    ManualCourtAssignment, CoachFeedback
)
# Import SoloSync models safely
try:
    from solosync_api.models import SoloSessionLog, SoloRoutine
    solosync_imported = True
except ImportError:
    print("Warning: Could not import SoloSync models. SoloSync features will be disabled.")
    SoloSessionLog = None
    SoloRoutine = None
    solosync_imported = False

# Import necessary forms
from .forms import (
    AttendanceForm, ActivityAssignmentForm, SessionAssessmentForm,
    CoachFeedbackForm, CourtSprintRecordForm, VolleyRecordForm,
    BackwallDriveRecordForm, MatchResultForm
)

# === Helper Function for Live Session State Calculation ===
def _get_live_session_state(session, effective_time):
    """
    Calculates the state of the session at a specific effective_time.
    Returns a dictionary suitable for JSON serialization, using millisecond timestamps.
    """
    state = {
        "currentTimeMillis": int(effective_time.timestamp() * 1000),
        "currentBlock": None,
        "nextBlock": None,
        "courtAssignments": {},
        "courtActivities": {},
        "nextRotationTimeMillis": None,
        "statusMessage": None
    }

    session_start_dt = session.start_datetime
    if not session_start_dt:
        state["statusMessage"] = "Session start time not defined."
        return state

    session_start_ms = int(session_start_dt.timestamp() * 1000)
    current_timestamp_ms = state["currentTimeMillis"]

    current_block_instance = None
    next_block_instance = None
    earliest_next_start_ms = float('inf')

    time_blocks = session.time_blocks.order_by('start_offset_minutes')

    # Pre-calculate block start/end times in milliseconds
    block_times = []
    for block in time_blocks:
        offset_ms = block.start_offset_minutes * 60 * 1000
        duration_ms = block.duration_minutes * 60 * 1000
        block_start_ms = session_start_ms + offset_ms
        block_end_ms = block_start_ms + duration_ms
        block_times.append({
            'instance': block,
            'blockStartMs': block_start_ms,
            'blockEndMs': block_end_ms
        })

    # Find current and next block
    for block_data in block_times:
        block = block_data['instance']
        block_start_ms = block_data['blockStartMs']
        block_end_ms = block_data['blockEndMs']
        block.blockStartMs = block_start_ms # Temporarily attach for helper functions
        block.blockEndMs = block_end_ms   # Temporarily attach for helper functions

        if block_start_ms <= current_timestamp_ms < block_end_ms:
            current_block_instance = block

        if block_start_ms > current_timestamp_ms:
            if block_start_ms < earliest_next_start_ms:
                earliest_next_start_ms = block_start_ms
                next_block_instance = block

    # --- Populate State Dictionary ---
    if current_block_instance:
        elapsed_time_in_block_ms = current_timestamp_ms - current_block_instance.blockStartMs

        state["currentBlock"] = {
            "id": current_block_instance.id,
            "blockStartMillis": current_block_instance.blockStartMs,
            "blockEndMillis": current_block_instance.blockEndMs,
            "focus": current_block_instance.block_focus or "N/A",
            "rotationInfo": f"Every {current_block_instance.rotation_interval_minutes} min" if current_block_instance.rotation_interval_minutes else "No rotation",
            "number_of_courts": current_block_instance.number_of_courts
        }

        # Calculate Assignments
        attendees = list(session.attendees.filter(is_active=True).order_by('last_name', 'first_name'))
        manual_assignments_qs = ManualCourtAssignment.objects.filter(
            time_block=current_block_instance,
            player__in=attendees
        )
        block_manuals = {ma.player_id: ma.court_number for ma in manual_assignments_qs}
        manually_assigned_player_ids = set(block_manuals.keys())

        calculated_assignments = defaultdict(list)
        num_courts = current_block_instance.number_of_courts
        for i in range(1, num_courts + 1):
            calculated_assignments[i] = []

        # Place manual
        for player in attendees:
            if player.id in block_manuals:
                target_court = block_manuals[player.id]
                if target_court in calculated_assignments:
                    calculated_assignments[target_court].append({"id": player.id, "name": player.full_name})

        # Auto/Rotate remaining
        players_to_auto = [p for p in attendees if p.id not in manually_assigned_player_ids]
        if players_to_auto and num_courts > 0:
            interval_min = current_block_instance.rotation_interval_minutes
            if interval_min and interval_min > 0:
                interval_ms = interval_min * 60 * 1000
                rotations = int(elapsed_time_in_block_ms // interval_ms)
                for idx, player in enumerate(players_to_auto):
                    court_idx = (idx + rotations) % num_courts
                    target_court = court_idx + 1
                    if target_court in calculated_assignments:
                        calculated_assignments[target_court].append({"id": player.id, "name": player.full_name})
            else: # Simple split
                for idx, player in enumerate(players_to_auto):
                    target_court = (idx % num_courts) + 1
                    if target_court in calculated_assignments:
                        calculated_assignments[target_court].append({"id": player.id, "name": player.full_name})

        # Sort and add to state
        for court_num in calculated_assignments:
            calculated_assignments[court_num].sort(key=lambda p: p['name'])
            state["courtAssignments"][court_num] = calculated_assignments[court_num]

        # Find Activities for current block
        activities_qs = ActivityAssignment.objects.filter(
            time_block=current_block_instance
        ).select_related('drill', 'lead_coach')
        for act in activities_qs:
            if act.court_number in calculated_assignments or act.court_number <= num_courts:
                 state["courtActivities"][act.court_number] = {
                     "name": act.drill.name if act.drill else act.custom_activity_name,
                     "coach": act.lead_coach.name if act.lead_coach else None
                 }

        # Calculate Next Rotation Time (as milliseconds)
        interval_min = current_block_instance.rotation_interval_minutes
        if interval_min and interval_min > 0:
            interval_ms = interval_min * 60 * 1000
            rotations = int(elapsed_time_in_block_ms // interval_ms)
            next_rotation_start_ms = current_block_instance.blockStartMs + (rotations + 1) * interval_ms
            if next_rotation_start_ms < current_block_instance.blockEndMs:
                state["nextRotationTimeMillis"] = next_rotation_start_ms

    else: # No current block
        if effective_time < session_start_dt:
            state["statusMessage"] = f"Session starts at {session_start_dt.strftime('%H:%M')}."
        else:
            state["statusMessage"] = "Session has ended."

    if next_block_instance:
        state["nextBlock"] = {
            "id": next_block_instance.id,
            "blockStartMillis": next_block_instance.blockStartMs,
            "blockEndMillis": next_block_instance.blockEndMs,
            "focus": next_block_instance.block_focus or "N/A"
        }
    elif current_block_instance: # If currently in the last block
         state["nextBlock"] = {"focus": "Final block of the session."}

    return state
# === END Helper Function ===


# --- Live Session View (Simplified - Renders Template Shell) ---
# @login_required # Optional
def live_session_view(request, session_id):
    """ Renders the live session page shell. JS will fetch state updates via API. """
    session = get_object_or_404(Session.objects.select_related('school_group'), pk=session_id)
    now = timezone.now()

    # --- Time Simulation Logic ---
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

    # Format initial effective time for JS (AWARE, no microseconds)
    effective_time_iso_formatted = None
    if effective_time_aware:
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


# --- API View for Live Session Updates ---
@require_GET
def live_session_update_api(request, session_id):
    """ API endpoint called by JS to get the current state of the live session. """
    session = get_object_or_404(Session, pk=session_id)
    now = timezone.now()

    # Determine effective time (check for simulation parameter passed from JS)
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


# --- Homepage View ---
def homepage_view(request):
    """ Displays the main homepage / dashboard. """
    now = timezone.now()
    upcoming_sessions = Session.objects.filter(
        Q(session_date__gt=now.date()) | Q(session_date=now.date(), session_start_time__gte=now.time())
    ).select_related('school_group').order_by('session_date', 'session_start_time')[:5]

    feedback_window_start = now - timedelta(days=14)
    fifteen_days_ago = now.date() - timedelta(days=15)
    potential_sessions = Session.objects.filter(
        session_date__gte=fifteen_days_ago,
        session_date__lte=now.date(),
        assessments_complete=False
    ).select_related('school_group').order_by('-session_date', '-session_start_time')

    recent_sessions_for_feedback = []
    for session in potential_sessions:
        if session.end_datetime:
            end_dt_aware = session.end_datetime
            # Compare aware datetimes if USE_TZ=True
            if timezone.is_aware(end_dt_aware) and timezone.is_aware(feedback_window_start) and timezone.is_aware(now):
                if feedback_window_start <= end_dt_aware < now:
                    recent_sessions_for_feedback.append(session)
            # Compare naive datetimes if USE_TZ=False
            elif not timezone.is_aware(end_dt_aware) and not timezone.is_aware(feedback_window_start) and not timezone.is_aware(now):
                 if feedback_window_start.replace(tzinfo=None) <= end_dt_aware < now.replace(tzinfo=None):
                      recent_sessions_for_feedback.append(session)
        if len(recent_sessions_for_feedback) >= 5:
            break

    recent_solo_logs = []
    if solosync_imported and SoloSessionLog is not None:
        User = settings.AUTH_USER_MODEL
        try:
            recent_solo_logs = SoloSessionLog.objects.select_related(
                'player', 'routine'
            ).order_by('-completed_at')[:10]
        except FieldError as e:
            print(f"FieldError fetching SoloSessionLog: {e}")
        except Exception as e:
            print(f"Error fetching SoloSessionLog: {e}")

    context = {
        'upcoming_sessions': upcoming_sessions,
        'recent_sessions_for_feedback': recent_sessions_for_feedback,
        'recent_solo_logs': recent_solo_logs,
    }
    return render(request, 'planning/homepage.html', context)


# --- Activity Views ---
# @login_required
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

# @login_required
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

# @login_required
@require_POST
def delete_activity(request, activity_id):
    activity_instance = get_object_or_404(ActivityAssignment, pk=activity_id)
    session_id = activity_instance.time_block.session_id
    activity_name = str(activity_instance)
    activity_instance.delete()
    messages.success(request, f"Activity '{activity_name}' deleted successfully.")
    return redirect('planning:session_detail', session_id=session_id)


# --- Player Profile View ---
def player_profile(request, player_id):
    player = get_object_or_404(Player.objects.prefetch_related('school_groups'), pk=player_id)
    sessions_attended_qs = player.attended_sessions.filter(session_date__lte=timezone.now().date()).order_by('-session_date', '-session_start_time')
    attended_sessions_count = sessions_attended_qs.count()
    player_group_ids = player.school_groups.values_list('id', flat=True)
    total_relevant_sessions_count = 0
    attendance_percentage = None
    if player_group_ids:
        total_relevant_sessions_count = Session.objects.filter(school_group_id__in=player_group_ids, session_date__lte=timezone.now().date()).count()
        if total_relevant_sessions_count > 0:
            attendance_percentage = round((attended_sessions_count / total_relevant_sessions_count) * 100)
        elif attended_sessions_count == 0:
             attendance_percentage = None

    assessments = player.session_assessments.select_related('session', 'session__school_group').order_by('-date_recorded', '-session__session_start_time')
    sprints = player.sprint_records.select_related('session').order_by('date_recorded')
    volleys = player.volley_records.select_related('session').order_by('date_recorded')
    drives = player.drive_records.select_related('session').order_by('date_recorded')
    matches = player.match_results.select_related('session').order_by('-date')

    # Chart data preparation
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
        'player': player,
        'sessions_attended': sessions_attended_qs,
        'attended_sessions_count': attended_sessions_count,
        'total_relevant_sessions_count': total_relevant_sessions_count,
        'attendance_percentage': attendance_percentage,
        'assessments': assessments,
        'sprints': sprints,
        'volleys': volleys,
        'drives': drives,
        'matches': matches,
        'sprint_chart_data': dict(sprint_chart_data), # Convert back for JSON
        'volley_chart_data': dict(volley_chart_data),
        'drive_chart_data': dict(drive_chart_data),
    }
    return render(request, 'planning/player_profile.html', context)

# --- Assess Player Session View ---
# @login_required
def assess_player_session(request, session_id, player_id):
    session = get_object_or_404(Session, pk=session_id)
    player = get_object_or_404(Player, pk=player_id)
    assessment_instance = SessionAssessment.objects.filter(session=session, player=player).first()

    if assessment_instance and request.method != 'POST':
         return redirect('planning:edit_session_assessment', assessment_id=assessment_instance.id)

    if request.method == 'POST':
        form = SessionAssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.session = session
            assessment.player = player
            if not form.cleaned_data.get('date_recorded'):
                 assessment.date_recorded = session.session_date
            assessment.save()
            messages.success(request, f"Assessment added for {player.full_name} in session on {session.session_date}.")
            return redirect('planning:pending_assessments')
    else:
        form = SessionAssessmentForm()

    context = {
        'form': form,
        'session': session,
        'player': player,
        'assessment_instance': None,
        'page_title': f"Add Assessment for {player.full_name}"
    }
    return render(request, 'planning/assess_player_form.html', context)

# --- Edit Session Assessment View ---
# @login_required
def edit_session_assessment(request, assessment_id):
    assessment_instance = get_object_or_404(SessionAssessment, pk=assessment_id)
    player = assessment_instance.player
    session = assessment_instance.session

    if request.method == 'POST':
        form = SessionAssessmentForm(request.POST, instance=assessment_instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"Assessment for {player.full_name} (Session: {session.session_date}) updated.")
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

# --- Delete Session Assessment View ---
# @login_required
@require_POST
def delete_session_assessment(request, assessment_id):
    assessment_instance = get_object_or_404(SessionAssessment, pk=assessment_id)
    player = assessment_instance.player
    assessment_instance.delete()
    messages.success(request, "Session assessment deleted successfully.")
    return redirect('planning:player_profile', player_id=player.id)

# --- Assess Latest Session Redirect View ---
# @login_required
def assess_latest_session_redirect(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    latest_session = player.attended_sessions.order_by('-session_date', '-session_start_time').first()
    if latest_session:
        assessment_instance = SessionAssessment.objects.filter(session=latest_session, player=player).first()
        if assessment_instance:
             return redirect('planning:edit_session_assessment', assessment_id=assessment_instance.id)
        else:
             return redirect('planning:assess_player_session', session_id=latest_session.id, player_id=player.id)
    else:
        messages.warning(request, f"{player.full_name} has no recorded session attendance to assess.")
        return redirect('planning:player_profile', player_id=player.id)


# --- Pending Assessments View ---
# @login_required
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


# --- Coach Feedback Views ---
# @login_required
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

# @login_required
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

# @login_required
@require_POST
def delete_coach_feedback(request, feedback_id):
    feedback_instance = get_object_or_404(CoachFeedback, pk=feedback_id)
    player = feedback_instance.player
    feedback_instance.delete()
    messages.success(request, "Feedback entry deleted successfully.")
    return redirect('planning:player_profile', player_id=player.id)


# --- API Views ---
# @login_required # Add auth if needed
@require_POST
def update_manual_assignment_api(request):
    try:
        data = json.loads(request.body)
        player_id = data.get('player_id')
        time_block_id = data.get('time_block_id')
        court_number_str = data.get('court_number') # Get as string initially

        # *** ADDED: Convert court_number to int and validate ***
        if court_number_str is None:
             raise ValueError("Missing court_number")
        court_number = int(court_number_str) # Convert to integer

    except (json.JSONDecodeError, ValueError) as e: # Catch potential errors
        return JsonResponse({'status': 'error', 'message': f'Invalid data: {e}'}, status=400)

    if not all([player_id, time_block_id]): # court_number checked above
        return JsonResponse({'status': 'error', 'message': 'Missing player_id or time_block_id'}, status=400)

    try:
        player = Player.objects.get(pk=player_id)
        time_block = TimeBlock.objects.get(pk=time_block_id)
    except ObjectDoesNotExist: # Catch specific exceptions
        return JsonResponse({'status': 'error', 'message': 'Player or TimeBlock not found'}, status=404)

    # *** Now compare integers ***
    if court_number > time_block.number_of_courts or court_number < 1:
        return JsonResponse({'status': 'error', 'message': 'Invalid court number for this block'}, status=400)

    try:
        assignment, created = ManualCourtAssignment.objects.update_or_create(
            time_block=time_block,
            player=player,
            defaults={'court_number': court_number}
        )
        return JsonResponse({'status': 'success', 'message': 'Assignment updated'})
    except Exception as e: # Catch potential database errors during save
        print(f"Error saving manual assignment: {e}") # Log the error server-side
        return JsonResponse({'status': 'error', 'message': 'Could not save assignment.'}, status=500)


# @login_required # Add auth if needed
@require_POST
def clear_manual_assignments_api(request, time_block_id):
    deleted_count, _ = ManualCourtAssignment.objects.filter(time_block_id=time_block_id).delete()
    return JsonResponse({'status': 'success', 'message': f'{deleted_count} manual assignments cleared.'})


# --- SoloSync Log List View (Replacing Placeholder) ---
# @login_required # Optional: Add if only coaches should see this
def solosync_log_list_view(request):
    """ Displays a list of all submitted SoloSync session logs. """
    log_list = []
    if solosync_imported and SoloSessionLog is not None:
        # Fetch all logs, ordered by completion date, newest first
        # Select related player and routine for display efficiency
        log_list = SoloSessionLog.objects.select_related(
            'player', 'routine'
        ).order_by('-completed_at')
        # TODO: Add pagination for potentially large lists
        # paginator = Paginator(log_list, 25) # Show 25 logs per page
        # page_number = request.GET.get('page')
        # page_obj = paginator.get_page(page_number)

    else:
        messages.warning(request, "SoloSync models not available.")
        # Optionally redirect or show a specific message

    context = {
        'solo_session_logs': log_list, # Use page_obj if using pagination
        'page_title': "SoloSync Session Logs"
    }
    # We need to create this template next
    return render(request, 'planning/solosync_log_list.html', context)


# ... other metric form views (add_sprint_record, add_volley_record, etc.) ...
def add_sprint_record(request, player_id):
     player = get_object_or_404(Player, pk=player_id)
     if request.method == 'POST':
         form = CourtSprintRecordForm(request.POST)
         if form.is_valid():
             record = form.save(commit=False); record.player = player; record.save()
             messages.success(request, "Sprint record saved.")
             return redirect('planning:player_profile', player_id=player.id)
     else: form = CourtSprintRecordForm()
     context = {'form': form, 'player': player, 'page_title': 'Add Sprint Record'}
     return render(request, 'planning/add_sprint_form.html', context)

def add_volley_record(request, player_id):
     player = get_object_or_404(Player, pk=player_id)
     if request.method == 'POST':
         form = VolleyRecordForm(request.POST)
         if form.is_valid():
             record = form.save(commit=False); record.player = player; record.save()
             messages.success(request, "Volley record saved.")
             return redirect('planning:player_profile', player_id=player.id)
     else: form = VolleyRecordForm()
     context = {'form': form, 'player': player, 'page_title': 'Add Volley Record'}
     return render(request, 'planning/add_volley_form.html', context)

def add_drive_record(request, player_id):
     player = get_object_or_404(Player, pk=player_id)
     if request.method == 'POST':
         form = BackwallDriveRecordForm(request.POST)
         if form.is_valid():
             record = form.save(commit=False); record.player = player; record.save()
             messages.success(request, "Drive record saved.")
             return redirect('planning:player_profile', player_id=player.id)
     else: form = BackwallDriveRecordForm()
     context = {'form': form, 'player': player, 'page_title': 'Add Drive Record'}
     return render(request, 'planning/add_drive_form.html', context)

def add_match_result(request, player_id):
     player = get_object_or_404(Player, pk=player_id)
     if request.method == 'POST':
         form = MatchResultForm(request.POST)
         if form.is_valid():
             record = form.save(commit=False); record.player = player; record.save()
             messages.success(request, "Match result saved.")
             return redirect('planning:player_profile', player_id=player.id)
     else: form = MatchResultForm()
     context = {'form': form, 'player': player, 'page_title': 'Add Match Result'}
     return render(request, 'planning/add_match_form.html', context)

# Session List View
def session_list(request):
    all_sessions = Session.objects.select_related('school_group').order_by('-session_date', '-session_start_time')
    context = {'sessions_list': all_sessions, 'page_title': 'All Sessions'}
    return render(request, 'planning/session_list.html', context)

# Session Detail View
def session_detail(request, session_id):
    session = get_object_or_404(Session.objects.prefetch_related('time_blocks'), pk=session_id)
    time_blocks = session.time_blocks.all() # Already prefetched
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
            # Clear manual assignments when attendance changes
            ManualCourtAssignment.objects.filter(time_block__session=session).delete()
            messages.success(request, "Attendance updated.")
            return redirect('planning:session_detail', session_id=session.id)

    # Calculate Assignments Per Block (Merge Manual over Auto)
    block_data = []
    display_attendees = session.attendees.all().order_by('last_name', 'first_name') # Re-query after potential update
    if display_attendees.exists() and school_group_for_session:
        # Fetch all manual assignments for this session once
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
                 # Find the player object (consider prefetching display_attendees with IDs)
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
        'current_attendees': display_attendees, # Use the potentially updated list
        'block_data': block_data,
        'page_title': f"Session Plan: {session}"
    }
    return render(request, 'planning/session_detail.html', context)

# Player List View
def players_list_view(request):
    groups = SchoolGroup.objects.all().order_by('name')
    selected_group_id = request.GET.get('group')
    search_query = request.GET.get('search', '') # Get search query, default to empty

    players = Player.objects.filter(is_active=True) # Start with active players

    # Filter by selected group if an ID is provided
    if selected_group_id:
        players = players.filter(school_groups__id=selected_group_id)
        page_title = f"Players in {get_object_or_404(SchoolGroup, pk=selected_group_id).name}"
    else:
        page_title = "All Active Players"

     # Filter by search query if provided
    if search_query:
         players = players.filter(
             Q(first_name__icontains=search_query) | Q(last_name__icontains=search_query)
         )
         # Append search term to title if filtering by group as well
         if selected_group_id:
             page_title += f" matching '{search_query}'"
         else:
             page_title = f"Active Players matching '{search_query}'"


    players = players.order_by('last_name', 'first_name').distinct()

    context = {
        'players': players,
        'groups': groups,
        'selected_group_id': selected_group_id,
        'search_query': search_query, # Pass search query back to template
        'page_title': page_title,
    }
    return render(request, 'planning/players_list.html', context)

# --- Helper for calculating groups (remains internal) ---
def _calculate_skill_priority_groups(players, num_courts):
    # Simple implementation: Sort by skill (Adv > Int > Beg), then name, then deal out
    skill_order = {Player.SkillLevel.ADVANCED: 0, Player.SkillLevel.INTERMEDIATE: 1, Player.SkillLevel.BEGINNER: 2}
    sorted_players = sorted(
        players,
        key=lambda p: (skill_order.get(p.skill_level, 3), p.last_name, p.first_name)
    )
    groups = defaultdict(list)
    if num_courts <= 0: # Avoid division by zero
        return dict(groups)
    for i, player in enumerate(sorted_players):
        court_num = (i % num_courts) + 1
        groups[court_num].append(player)
    return dict(groups)

# One Page Plan View
def one_page_plan_view(request, session_id):
    session = get_object_or_404(Session.objects.select_related('school_group').prefetch_related('coaches_attending'), pk=session_id)
    time_blocks = session.time_blocks.order_by('start_offset_minutes')
    activities = ActivityAssignment.objects.filter(
        time_block__session=session
    ).select_related('drill', 'lead_coach').order_by('time_block__start_offset_minutes', 'court_number', 'order')
    coaches = session.coaches_attending.all()

    context = {
        'session': session,
        'time_blocks': time_blocks,
        'activities': activities,
        'coaches': coaches,
    }
    return render(request, 'planning/one_page_plan.html', context)

