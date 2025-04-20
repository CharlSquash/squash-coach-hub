# planning/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.db.models import Q
# Import all necessary models and the forms
from .models import ( Session, ActivityAssignment, TimeBlock, Drill, Coach, Player,
                      SchoolGroup, SessionAssessment, CourtSprintRecord, VolleyRecord,
                      BackwallDriveRecord, MatchResult )
from .forms import ( ActivityAssignmentForm, AttendanceForm, SessionAssessmentForm,
                     CourtSprintRecordForm, VolleyRecordForm, BackwallDriveRecordForm,
                     MatchResultForm )
import math
import datetime
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

# --- Helper function _calculate_skill_priority_groups ---
def _calculate_skill_priority_groups(attendees_queryset, num_courts):
    """
    Groups players prioritizing same-skill groups first, then distributes
    remainders as evenly as possible. Rewritten for formatting.
    Returns a dictionary: {court_num: [player_list]}
    """
    assignments = {}
    if not attendees_queryset or num_courts <= 0:
        return assignments

    # Separate by Skill Level
    adv_players = list(attendees_queryset.filter(skill_level=Player.SkillLevel.ADVANCED).order_by('last_name', 'first_name'))
    int_players = list(attendees_queryset.filter(skill_level=Player.SkillLevel.INTERMEDIATE).order_by('last_name', 'first_name'))
    beg_players = list(attendees_queryset.filter(skill_level=Player.SkillLevel.BEGINNER).order_by('last_name', 'first_name'))

    num_total = len(adv_players) + len(int_players) + len(beg_players)
    if num_total == 0:
        return assignments

    # Determine Target Group Sizes
    base_size = num_total // num_courts
    num_large_groups = num_total % num_courts
    court_targets = [base_size + 1] * num_large_groups + [base_size] * (num_courts - num_large_groups)

    current_court_index = 0
    player_lists = [adv_players, int_players, beg_players]

    # Allocate Homogeneous groups
    for player_list in player_lists:
        while current_court_index < num_courts:
            target_size = court_targets[current_court_index]
            if target_size > 0 and len(player_list) >= target_size:
                group = player_list[:target_size]
                assignments[current_court_index + 1] = group
                # Remove assigned players (slice assignment modifies original list)
                player_list[:] = player_list[target_size:]
                # Move to next court slot
                current_court_index += 1
            else:
                # Cannot form a full group of this skill level, move to next skill
                break # Exit the inner while loop (for this skill level)

    # Handle Leftovers
    remaining_players = adv_players + int_players + beg_players
    player_idx = 0
    while current_court_index < num_courts:
        court_num = current_court_index + 1
        target_size = court_targets[current_court_index]
        current_group = assignments.get(court_num, [])
        while len(current_group) < target_size and player_idx < len(remaining_players):
            current_group.append(remaining_players[player_idx])
            player_idx += 1
        # Ensure the court exists in assignments even if it was initially empty and got no leftovers
        if current_group or court_num not in assignments:
             assignments[court_num] = current_group
        current_court_index += 1

    # Distribute final stragglers if any (should be rare)
    court_idx_final_pass = 0
    while player_idx < len(remaining_players):
        court_num_final = (court_idx_final_pass % num_courts) + 1
        # Ensure court exists in dictionary before appending
        if court_num_final not in assignments:
            assignments[court_num_final] = []
        assignments[court_num_final].append(remaining_players[player_idx])
        player_idx += 1
        court_idx_final_pass += 1

    # Ensure all courts up to num_courts exist in the dictionary, even if empty
    for i in range(1, num_courts + 1):
        if i not in assignments:
            assignments[i] = []

    return assignments

# --- Session List View ---
def session_list(request):
    all_sessions = Session.objects.all().order_by('-date', '-start_time')
    context = {'sessions_list': all_sessions}
    return render(request, 'planning/session_list.html', context)

# --- Session Detail View ---
def session_detail(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    time_blocks = session.time_blocks.all()
    current_attendees = session.attendees.all().order_by('last_name', 'first_name')
    school_group_for_session = session.school_group
    activities = ActivityAssignment.objects.filter(
        time_block__session=session
    ).select_related('drill', 'lead_coach').order_by(
        'time_block__start_offset_minutes', 'court_number', 'order'
    )

    # Initialize form based on GET or POST
    initial_attendance = {'attendees': current_attendees}
    # Default to initializing with initial data (for GET or non-attendance POST)
    attendance_form = AttendanceForm(initial=initial_attendance, school_group=school_group_for_session)

    # Handle POST request specifically for attendance update
    if request.method == 'POST' and 'update_attendance' in request.POST:
        attendance_form = AttendanceForm(request.POST, school_group=school_group_for_session)
        if attendance_form.is_valid():
            selected_players = attendance_form.cleaned_data['attendees']
            session.attendees.set(selected_players)
            # Reload attendees after update before calculating groups
            current_attendees = session.attendees.all().order_by('last_name', 'first_name')
            # Re-initialize form with updated data for display after redirect
            initial_attendance = {'attendees': current_attendees}
            attendance_form = AttendanceForm(initial=initial_attendance, school_group=school_group_for_session)
            # Redirect to prevent re-POST on refresh
            return redirect('planning:session_detail', session_id=session.id)
        # If invalid, the form with errors (attendance_form) will be passed to context below

    # Calculate Assignments Per Block (for GET or if POST wasn't attendance update)
    block_data = []
    display_attendees = current_attendees # Use the possibly updated list
    if display_attendees.exists() and school_group_for_session:
        for block in time_blocks:
            assignments_for_block = _calculate_skill_priority_groups(
                display_attendees, block.number_of_courts
            )
            block_data.append({
                'block': block,
                'assignments': assignments_for_block
            })

    context = {
        'session': session,
        'activities': activities,
        'attendance_form': attendance_form, # Contains initial data or errors+POST data
        'current_attendees': display_attendees,
        'block_data': block_data,
    }
    return render(request, 'planning/session_detail.html', context)


# --- Live Session View ---
def live_session_view(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    time_blocks = session.time_blocks.all()
    current_attendees = session.attendees.all()
    activities = ActivityAssignment.objects.filter(
        time_block__session=session
    ).select_related('drill', 'lead_coach').order_by('order')

    # --- Determine Effective Time ---
    sim_time_str = request.GET.get('sim_time', None)
    effective_time = None
    is_simulated = False
    parsed_time = None

    if sim_time_str:
        try:
            # Try parsing datetime-local format first (naive)
            naive_dt = datetime.datetime.strptime(sim_time_str, '%Y-%m-%dT%H:%M')
            # Make aware using Django settings
            parsed_time = make_aware(naive_dt)
        except (ValueError, TypeError):
            try:
                # If previous failed, try full ISO format (aware)
                parsed_time = parse_datetime(sim_time_str)
            except (ValueError, TypeError):
                 # All parsing failed
                 pass # parsed_time remains None

        # Check if any parsing method succeeded
        if parsed_time:
             effective_time = parsed_time
             is_simulated = True

    # Fallback to current time if no valid simulation time provided/parsed
    if effective_time is None:
        effective_time = timezone.now()
        is_simulated = False # Ensure flag is False if using real time
    # --- End Determine Effective Time ---

    # --- Find Current/Next Block and calculate assignments ---
    current_block_data = None
    next_block_data = None
    processed_block_data = []

    # Calculate initial grouping based on attendees
    initial_assignments = {}
    if current_attendees.exists() and time_blocks.exists():
         first_block_courts = time_blocks.first().number_of_courts
         initial_assignments = _calculate_skill_priority_groups(current_attendees, first_block_courts)
         # Ensure it's a dict even if calculation returns None/empty
         if not initial_assignments:
             initial_assignments = {}

    # Process each block
    for i, block in enumerate(time_blocks):
        block_start_dt = block.block_start_datetime
        block_end_dt = block.block_end_datetime
        num_courts = block.number_of_courts
        block_activities = activities.filter(time_block=block)
        interval = block.rotation_interval_minutes

        # Calculate the base assignment for THIS block's court count
        base_assignments_for_block = {}
        if current_attendees.exists() and num_courts > 0:
             base_assignments_for_block = _calculate_skill_priority_groups(current_attendees, num_courts)

        # Start with base assignment, override if rotating
        current_display_assignments = base_assignments_for_block
        is_current = False

        # Check if block is currently active
        if block_start_dt and block_end_dt and block_start_dt <= effective_time < block_end_dt:
            is_current = True
            # Apply Rotation if applicable
            if interval and interval > 0 and base_assignments_for_block and num_courts > 0:
                minutes_into_block = 0.0
                # Calculate minutes into block safely
                if effective_time >= block_start_dt:
                    try:
                        if timezone.is_aware(effective_time) and timezone.is_aware(block_start_dt):
                             minutes_into_block = (effective_time - block_start_dt).total_seconds() / 60.0
                    except TypeError:
                        minutes_into_block = 0.0 # Fallback

                # Calculate rotation cycle safely
                rotation_cycle = 0
                try:
                    if minutes_into_block >= 0 and interval > 0: # Ensure interval > 0
                        rotation_cycle = math.floor(minutes_into_block / float(interval))
                    else:
                        rotation_cycle = 0
                except (TypeError, ValueError):
                    rotation_cycle = 0

                # Apply rotation if needed
                if rotation_cycle > 0:
                    rotated_assignments_temp = {}
                    initial_group_keys = sorted(list(base_assignments_for_block.keys()))
                    num_initial_groups = len(initial_group_keys)
                    if num_initial_groups > 0:
                        for court_num_target in range(1, num_courts + 1):
                            if court_num_target in initial_group_keys:
                                original_court_index = (((court_num_target - 1) - rotation_cycle) % num_courts) % num_initial_groups
                                original_group_key = initial_group_keys[original_court_index]
                                rotated_assignments_temp[court_num_target] = base_assignments_for_block.get(original_group_key, [])
                            else:
                                rotated_assignments_temp[court_num_target] = []
                        current_display_assignments = rotated_assignments_temp

        # Prepare data for this block
        block_info = {
            'block': block,
            'assignments': current_display_assignments,
            'start_dt': block_start_dt,
            'end_dt': block_end_dt,
            'block_activities': block_activities
        }
        processed_block_data.append(block_info)

        # Update current/next block pointers
        if is_current:
            current_block_data = block_info
        elif not current_block_data and block_start_dt and block_start_dt > effective_time:
             if next_block_data is None:
                 next_block_data = block_info

    # Handle edge case where session hasn't started
    if not current_block_data and not next_block_data and processed_block_data:
         next_block_data = processed_block_data[0]

    # Prepare final context
    context = {
        'session': session,
        'current_block_data': current_block_data,
        'next_block_data': next_block_data,
        'effective_time': effective_time,
        'is_simulated': is_simulated,
        'sim_time_value': effective_time.strftime('%Y-%m-%dT%H:%M')
    }
    return render(request, 'planning/live_session.html', context)


# --- Add/Edit/Delete Activity Views ---
def add_activity(request, block_id, court_num):
    block = get_object_or_404(TimeBlock, pk=block_id)
    session = block.session
    form = ActivityAssignmentForm() # Initialize for GET or invalid POST

    if request.method == 'POST':
        form = ActivityAssignmentForm(request.POST)
        if form.is_valid():
            submitted_duration = form.cleaned_data.get('duration_minutes') or 0
            existing_activities = ActivityAssignment.objects.filter(time_block=block, court_number=court_num)
            total_existing_duration = sum(act.duration_minutes for act in existing_activities)
            new_total_duration = total_existing_duration + submitted_duration
            if new_total_duration > block.duration_minutes:
                form.add_error(None, f"Adding activity ({submitted_duration}m) exceeds block duration ({block.duration_minutes}m) for Court {court_num}. Used: {total_existing_duration}m.")
            else:
                new_activity = form.save(commit=False)
                new_activity.time_block = block
                new_activity.court_number = court_num
                new_activity.save()
                return redirect('planning:session_detail', session_id=block.session.id)
        # Fall through to render form if invalid

    context = {
        'form': form, # Contains POST data and errors if invalid POST
        'time_block': block,
        'court_num': court_num,
        'session': session
    }
    return render(request, 'planning/add_activity_form.html', context)

def edit_activity(request, activity_id):
    activity_to_edit = get_object_or_404(ActivityAssignment, pk=activity_id)
    block = activity_to_edit.time_block
    session = block.session
    court_num = activity_to_edit.court_number
    form = ActivityAssignmentForm(instance=activity_to_edit) # Initialize for GET

    if request.method == 'POST':
        form = ActivityAssignmentForm(request.POST, instance=activity_to_edit)
        if form.is_valid():
            submitted_duration = form.cleaned_data.get('duration_minutes') or 0
            existing_activities = ActivityAssignment.objects.filter(time_block=block, court_number=court_num).exclude(pk=activity_id)
            total_existing_duration = sum(act.duration_minutes for act in existing_activities)
            new_total_duration = total_existing_duration + submitted_duration
            if new_total_duration > block.duration_minutes:
                 form.add_error(None, f"Saving activity ({submitted_duration}m) exceeds block duration ({block.duration_minutes}m) for Court {court_num}. Others: {total_existing_duration}m.")
            else:
                form.save()
                return redirect('planning:session_detail', session_id=session.id)
        # Fall through to render form if invalid

    context = {
        'form': form, # Contains instance data (GET) or errors+POST data (invalid POST)
        'activity': activity_to_edit,
        'time_block': block,
        'court_num': court_num,
        'session': session
    }
    return render(request, 'planning/edit_activity_form.html', context)

def delete_activity(request, activity_id):
    activity_to_delete = get_object_or_404(ActivityAssignment, pk=activity_id)
    session_id = activity_to_delete.time_block.session.id
    if request.method == 'POST':
        activity_to_delete.delete()
        return redirect('planning:session_detail', session_id=session_id)
    # GET request shows confirmation page
    context = {'activity': activity_to_delete, 'session_id': session_id}
    return render(request, 'planning/delete_activity_confirm.html', context)


# --- Player Profile View ---
def player_profile(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    sessions_attended = player.sessions_attended.order_by('-date', '-start_time')
    assessments = player.session_assessments.select_related('session', 'session__school_group').order_by('-date_recorded', '-session__start_time')
    # Order metrics by date for charting
    sprints = player.sprint_records.select_related('session').order_by('date_recorded')
    volleys = player.volley_records.select_related('session').order_by('date_recorded')
    drives = player.drive_records.select_related('session').order_by('date_recorded')
    matches = player.match_results.select_related('session').order_by('-date')

    # Prepare Data for Charts - create Python Dicts
    sprint_chart_data = {'3m': {'labels': [], 'data': []}, '5m': {'labels': [], 'data': []}, '10m': {'labels': [], 'data': []}}
    for sprint in sprints:
        key = sprint.duration_choice
        if key in sprint_chart_data:
            sprint_chart_data[key]['labels'].append(sprint.date_recorded)
            sprint_chart_data[key]['data'].append(sprint.score)

    volley_chart_data = {'FH': {'labels': [], 'data': []}, 'BH': {'labels': [], 'data': []}}
    for volley in volleys:
        key = volley.shot_type
        if key in volley_chart_data:
            volley_chart_data[key]['labels'].append(volley.date_recorded)
            volley_chart_data[key]['data'].append(volley.consecutive_count)

    drive_chart_data = {'FH': {'labels': [], 'data': []}, 'BH': {'labels': [], 'data': []}}
    for drive in drives:
        key = drive.shot_type
        if key in drive_chart_data:
            drive_chart_data[key]['labels'].append(drive.date_recorded)
            drive_chart_data[key]['data'].append(drive.consecutive_count)

    # Pass the Python dictionaries DIRECTLY to the context
    context = {
        'player': player,
        'sessions_attended': sessions_attended,
        'assessments': assessments,
        'sprints': sprints, # Keep raw data for tables
        'volleys': volleys,
        'drives': drives,
        'matches': matches,
        # Pass structured data for charts (json_script handles conversion)
        'sprint_chart_data': sprint_chart_data,
        'volley_chart_data': volley_chart_data,
        'drive_chart_data': drive_chart_data,
    }
    return render(request, 'planning/player_profile.html', context)

# --- Session Assessment View ---
def assess_player_session(request, session_id, player_id):
    session = get_object_or_404(Session, pk=session_id)
    player = get_object_or_404(Player, pk=player_id)
    # Check if player actually attended the session
    if not session.attendees.filter(pk=player.id).exists():
        # Add a message here later if desired using django.contrib.messages
        return redirect('planning:session_detail', session_id=session.id)
    assessment_instance = SessionAssessment.objects.filter(session=session, player=player).first()

    form = SessionAssessmentForm(instance=assessment_instance) # Initialize for GET
    if request.method == 'POST':
        form = SessionAssessmentForm(request.POST, instance=assessment_instance)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.session = session
            assessment.player = player
            assessment.date_recorded = session.date # Use session date
            assessment.save()
            return redirect('planning:session_detail', session_id=session.id)
        # If invalid POST, fall through to render form with errors

    context = {
        'form': form,
        'player': player,
        'session': session,
        'assessment_instance': assessment_instance
    }
    return render(request, 'planning/assess_player_form.html', context)


# --- Add Metric/Match Views ---
def add_sprint_record(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    form = CourtSprintRecordForm() # Initialize for GET or invalid POST
    if request.method == 'POST':
        form = CourtSprintRecordForm(request.POST)
        if form.is_valid():
            sprint_record = form.save(commit=False)
            sprint_record.player = player
            sprint_record.save()
            return redirect('planning:player_profile', player_id=player.id)
        # If invalid POST, fall through to render form with errors

    context = {'form': form, 'player': player }
    return render(request, 'planning/add_sprint_form.html', context)

def add_volley_record(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    form = VolleyRecordForm() # Initialize for GET or invalid POST
    if request.method == 'POST':
        form = VolleyRecordForm(request.POST)
        if form.is_valid():
            volley_record = form.save(commit=False)
            volley_record.player = player
            volley_record.save()
            return redirect('planning:player_profile', player_id=player.id)
        # If invalid POST, fall through

    context = {'form': form, 'player': player}
    return render(request, 'planning/add_volley_form.html', context)

def add_drive_record(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    form = BackwallDriveRecordForm() # Initialize for GET or invalid POST
    if request.method == 'POST':
        form = BackwallDriveRecordForm(request.POST)
        if form.is_valid():
            drive_record = form.save(commit=False)
            drive_record.player = player
            drive_record.save()
            return redirect('planning:player_profile', player_id=player.id)
        # If invalid POST, fall through

    context = {'form': form, 'player': player}
    return render(request, 'planning/add_drive_form.html', context)

def add_match_result(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    form = MatchResultForm() # Initialize for GET or invalid POST
    if request.method == 'POST':
        form = MatchResultForm(request.POST)
        if form.is_valid():
            match_result = form.save(commit=False)
            match_result.player = player
            match_result.save()
            return redirect('planning:player_profile', player_id=player.id)
        # If invalid POST, fall through

    context = {'form': form, 'player': player}
    return render(request, 'planning/add_match_form.html', context)


# --- One-Page Plan View ---
def one_page_plan_view(request, session_id):
    """Displays a simplified, shareable view of the session plan."""
    session = get_object_or_404(Session, pk=session_id)
    # Fetch related data needed for the plan
    time_blocks = session.time_blocks.all().order_by('start_offset_minutes')
    # Fetch all activities for the session, ordered correctly
    activities = ActivityAssignment.objects.filter(
        time_block__session=session
    ).select_related('drill', 'lead_coach').order_by(
        'time_block__start_offset_minutes', 'court_number', 'order'
    )
    coaches = session.coaches_attending.all()

    context = {
        'session': session,
        'time_blocks': time_blocks,
        'activities': activities, # Pass all activities, filter in template
        'coaches': coaches,
    }
    return render(request, 'planning/one_page_plan.html', context) # New template

# --- Homepage View ---
def homepage_view(request):
    """Displays the main homepage / dashboard."""
    now = timezone.now()
    # Query for upcoming sessions (date >= today AND time >= now if date is today)
    upcoming_sessions = Session.objects.filter(
        Q(date__gt=now.date()) | Q(date=now.date(), start_time__gte=now.time())
    ).select_related('school_group').order_by('date', 'start_time')[:5] # Show next 5

    context = {
        'upcoming_sessions': upcoming_sessions
        # Add other data needed for homepage here later
    }
    return render(request, 'planning/homepage.html', context) # New template

# End of file - ensure no extra text below this line
