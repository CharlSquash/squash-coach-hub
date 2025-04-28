# planning/views.py
# Fixed logic to merge manual assignments over automatic grouping.
# Strict formatting applied.

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone # Django's timezone utilities
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden, Http404 # Added Http404
from django.views.decorators.http import require_POST # To ensure POST requests
from .models import Player, CoachFeedback 
from datetime import timedelta, datetime, time
from .forms import CoachFeedbackForm 
from .models import Session
from django.db.models import Q, Prefetch
from collections import defaultdict
from django.contrib import messages
# from django.views.decorators.csrf import csrf_exempt # REMOVED

# Import all necessary models and the forms
from .models import ( Session, ActivityAssignment, TimeBlock, Drill, Coach, Player,
                      SchoolGroup, SessionAssessment, CourtSprintRecord, VolleyRecord,
                      BackwallDriveRecord, MatchResult, ManualCourtAssignment )
from .forms import ( ActivityAssignmentForm, AttendanceForm, SessionAssessmentForm,
                     CourtSprintRecordForm, VolleyRecordForm, BackwallDriveRecordForm,
                     MatchResultForm )
import math
import datetime
# Import timezone object from standard datetime library for UTC
from datetime import timezone as dt_timezone # Alias to avoid name clash
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware # Keep Django's make_aware
from pathlib import Path
import os
from collections import defaultdict # Used for merging assignments

# --- Helper function _calculate_skill_priority_groups ---
# (Remains the same - correctly formatted)
def _calculate_skill_priority_groups(attendees_queryset, num_courts):
    assignments = {}
    if not attendees_queryset or num_courts <= 0:
        # Ensure all court keys exist even if no players
        for i in range(1, num_courts + 1):
            assignments[i] = []
        return assignments

    # Convert queryset to list to avoid modifying original during processing
    attendee_list = list(attendees_queryset)

    adv_players = [p for p in attendee_list if p.skill_level == Player.SkillLevel.ADVANCED]
    adv_players.sort(key=lambda p: (p.last_name, p.first_name))
    int_players = [p for p in attendee_list if p.skill_level == Player.SkillLevel.INTERMEDIATE]
    int_players.sort(key=lambda p: (p.last_name, p.first_name))
    beg_players = [p for p in attendee_list if p.skill_level == Player.SkillLevel.BEGINNER]
    beg_players.sort(key=lambda p: (p.last_name, p.first_name))

    num_total = len(attendee_list)
    if num_total == 0:
         # Ensure all court keys exist even if no players
        for i in range(1, num_courts + 1):
            assignments[i] = []
        return assignments

    base_size = num_total // num_courts
    num_large_groups = num_total % num_courts
    court_targets = [base_size + 1] * num_large_groups + [base_size] * (num_courts - num_large_groups)

    current_court_index = 0
    player_lists = [adv_players, int_players, beg_players] # Process in skill order

    # Initialize assignments dictionary with empty lists for all courts
    for i in range(1, num_courts + 1):
        assignments[i] = []

    # Allocate Homogeneous groups first
    for player_list_group in player_lists:
        # Use a copy to iterate while modifying the original list
        players_to_assign = list(player_list_group)
        temp_assigned_indices = [] # Track indices to remove later

        for player_idx, player in enumerate(players_to_assign):
            assigned_this_round = False
            # Try to place player in the next available court that needs this skill level
            # This simple loop might not perfectly balance skill, but prioritizes full groups
            for court_idx_offset in range(num_courts):
                check_court_index = (current_court_index + court_idx_offset) % num_courts
                court_num = check_court_index + 1
                target_size = court_targets[check_court_index]

                if len(assignments[court_num]) < target_size:
                    assignments[court_num].append(player)
                    temp_assigned_indices.append(player_idx)
                    assigned_this_round = True
                    # Move the starting point for the next player of this skill level potentially
                    current_court_index = (check_court_index + 1) % num_courts
                    break # Player assigned, move to next player

            # If player couldn't be placed in a non-full group (should be rare with leftovers logic)
            # Keep track for leftover distribution (though the current logic might handle this)

        # Remove assigned players from the original list (by index in reverse)
        for index in sorted(temp_assigned_indices, reverse=True):
             player_list_group.pop(index)


    # Handle Leftovers (players remaining in adv/int/beg lists)
    remaining_players = adv_players + int_players + beg_players
    player_idx = 0
    # Fill remaining spots in courts sequentially
    for court_num in range(1, num_courts + 1):
        target_size = court_targets[court_num - 1] # Use original target size
        while len(assignments[court_num]) < target_size and player_idx < len(remaining_players):
            assignments[court_num].append(remaining_players[player_idx])
            player_idx += 1

    # Distribute any final stragglers (if total didn't divide perfectly or logic above missed some)
    court_idx_final_pass = 0
    while player_idx < len(remaining_players):
        court_num_final = (court_idx_final_pass % num_courts) + 1
        assignments[court_num_final].append(remaining_players[player_idx])
        player_idx += 1
        court_idx_final_pass += 1

    return assignments


# --- Session List View ---
def session_list(request):
    # Use the corrected field names 'session_date' and 'session_start_time'
    all_sessions = Session.objects.select_related('school_group').order_by('-session_date', '-session_start_time') # <-- CORRECTED
    context = {'sessions_list': all_sessions}
    return render(request, 'planning/session_list.html', context)

# planning/views.py
from django.shortcuts import render, get_object_or_404 # Import get_object_or_404
from .models import Player, SchoolGroup 

# ... other views ...

def players_list_view(request):
    """
    View to display a list of active players, allowing filtering by 
    school group and searching by name.
    """
    groups = SchoolGroup.objects.all().order_by('name')
    # Start with base queryset of active players
    players_qs = Player.objects.filter(is_active=True) # Renamed variable for clarity

    # --- Get Filter/Search Parameters ---
    selected_group_id = request.GET.get('group', None) 
    search_query = request.GET.get('search', None) # Get search query param
    selected_group = None 
    page_title_suffix = "" # To build dynamic title parts

    # --- Apply Group Filter (if selected) ---
    if selected_group_id and selected_group_id.isdigit():
        try:
            group_id_int = int(selected_group_id)
            players_qs = players_qs.filter(school_groups__id=group_id_int) # Filter the queryset
            selected_group = get_object_or_404(SchoolGroup, id=group_id_int)
            page_title_suffix += f" in {selected_group.name}"
        except SchoolGroup.DoesNotExist:
            selected_group_id = None # Reset if invalid group ID
    else:
        selected_group_id = None 

    # --- Apply Search Filter (if query exists) ---
    if search_query:
        # Filter the *already potentially filtered* queryset further
        # Use Q objects for case-insensitive OR search on first/last name
        players_qs = players_qs.filter(
            Q(first_name__icontains=search_query) | 
            Q(last_name__icontains=search_query)
        )
        page_title_suffix += f" matching '{search_query}'" # Add search info to title

    # --- Finalize Queryset (apply ordering AFTER filtering) ---
    players = players_qs.order_by('last_name', 'first_name') 

    # --- Determine Page Title ---
    if not selected_group_id and not search_query:
        page_title = 'All Active Players'
    else:
         page_title = f"Players{page_title_suffix}" # Construct title from applied filters

    # --- Prepare Context ---
    context = {
        'page_title': page_title,
        'players': players, # Pass final ordered list        
        'groups': groups,            
        'selected_group_id': selected_group_id, 
        'search_query': search_query # Pass search query back to template input field
    }
    return render(request, 'planning/players_list.html', context)
    
# --- Session Detail View ---
def session_detail(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    time_blocks = session.time_blocks.all()
    current_attendees = session.attendees.all().order_by('last_name', 'first_name')
    current_attendees_set = set(current_attendees)
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
            current_attendees = session.attendees.all().order_by('last_name', 'first_name')
            current_attendees_set = set(current_attendees)
            initial_attendance = {'attendees': current_attendees}
            attendance_form = AttendanceForm(initial=initial_attendance, school_group=school_group_for_session)
            # Clear manual assignments when attendance changes?
            ManualCourtAssignment.objects.filter(time_block__session=session).delete()
            return redirect('planning:session_detail', session_id=session.id)

    # Calculate Assignments Per Block (Merge Manual over Auto)
    block_data = []
    display_attendees = current_attendees
    if display_attendees.exists() and school_group_for_session:
        for block in time_blocks:
            # 1. Get Automatic assignments for ALL current attendees
            auto_assignments = _calculate_skill_priority_groups(
                display_attendees, block.number_of_courts
            )

            # 2. Get Manual assignments for this block
            manual_assignments_qs = ManualCourtAssignment.objects.filter(
                time_block=block, player__in=current_attendees # Only consider attending players
            ).select_related('player')

            final_assignments = defaultdict(list)
            # Copy auto assignments initially, ensuring all courts exist
            for court_num in range(1, block.number_of_courts + 1):
                 final_assignments[court_num] = list(auto_assignments.get(court_num, [])) # Use list copy

            manually_assigned_players = set()
            manual_assignments_map = {} # Store manual target: {player: court}

            if manual_assignments_qs.exists():
                for ma in manual_assignments_qs:
                    manually_assigned_players.add(ma.player)
                    manual_assignments_map[ma.player] = ma.court_number

                # 3. Merge: Remove manually assigned players from their auto spots
                #    and place them in their manual spots.
                for court_num in range(1, block.number_of_courts + 1):
                    current_court_list = final_assignments[court_num]
                    # Use list comprehension to filter out players who WILL be manually placed elsewhere
                    final_assignments[court_num] = [
                        p for p in current_court_list if p not in manually_assigned_players
                    ]

                # Place manually assigned players in their designated courts
                for player, target_court in manual_assignments_map.items():
                    # Avoid duplicates if somehow they were already there
                    if player not in final_assignments[target_court]:
                        final_assignments[target_court].append(player)

            # Sort player lists within each court for consistent display
            for court_num in final_assignments:
                 final_assignments[court_num].sort(key=lambda p: (p.last_name, p.first_name))

            block_data.append({
                'block': block,
                'assignments': dict(final_assignments), # Convert back to regular dict for template
                'has_manual': manual_assignments_qs.exists()
            })

    context = {
        'session': session,
        'activities': activities,
        'attendance_form': attendance_form,
        'current_attendees': display_attendees,
        'block_data': block_data,
    }
    return render(request, 'planning/session_detail.html', context)


# --- Live Session View ---
def live_session_view(request, session_id):
    session = get_object_or_404(Session, pk=session_id)
    time_blocks = session.time_blocks.all()
    current_attendees = session.attendees.all()
    current_attendees_set = set(current_attendees)
    activities = ActivityAssignment.objects.filter(
        time_block__session=session
    ).select_related('drill', 'lead_coach').order_by('order')

    # Determine Effective Time
    sim_time_str = request.GET.get('sim_time', None)
    effective_time = None
    is_simulated = False
    parsed_time = None

    if sim_time_str:
        try:
            naive_dt = datetime.datetime.strptime(sim_time_str, '%Y-%m-%dT%H:%M')
            parsed_time = timezone.make_aware(naive_dt, timezone.get_current_timezone())
            effective_time = timezone.localtime(parsed_time, dt_timezone.utc)
            is_simulated = True
        except (ValueError, TypeError):
            try:
                parsed_time_aware = parse_datetime(sim_time_str)
                if parsed_time_aware and timezone.is_aware(parsed_time_aware):
                     effective_time = timezone.localtime(parsed_time_aware, dt_timezone.utc)
                     is_simulated = True
                elif parsed_time_aware and timezone.is_naive(parsed_time_aware):
                    parsed_time = timezone.make_aware(parsed_time_aware, timezone.get_current_timezone())
                    effective_time = timezone.localtime(parsed_time, dt_timezone.utc)
                    is_simulated = True
            except (ValueError, TypeError):
                 pass

    if effective_time is None:
        effective_time = timezone.now()
        is_simulated = False

    local_effective_time = timezone.localtime(effective_time)
    sim_time_input_value = local_effective_time.strftime('%Y-%m-%dT%H:%M')

    # Find Current/Next Block, assignments, next rotation time
    current_block_data = None
    next_block_data = None
    processed_block_data = []
    next_rotation_time_iso = None
    display_next_rotation_time = None

    for i, block in enumerate(time_blocks):
        block_start_dt = block.block_start_datetime
        block_end_dt = block.block_end_datetime
        num_courts = block.number_of_courts
        block_activities = activities.filter(time_block=block)
        interval = block.rotation_interval_minutes

        # --- Determine Base Assignments (Manual or Auto) for THIS block ---
        base_assignments_for_block = defaultdict(list) # Use defaultdict
        manual_assignments_qs = ManualCourtAssignment.objects.filter(
            time_block=block, player__in=current_attendees # Only consider attending players
        ).select_related('player').order_by('court_number', 'player__last_name')

        manually_assigned_players = set()
        manual_assignments_map = {}

        if manual_assignments_qs.exists():
            for ma in manual_assignments_qs:
                manually_assigned_players.add(ma.player)
                manual_assignments_map[ma.player] = ma.court_number

            # Start with manual assignments
            for player, target_court in manual_assignments_map.items():
                 base_assignments_for_block[target_court].append(player)

            # Get unassigned attendees
            unassigned_attendees = current_attendees_set - manually_assigned_players
            if unassigned_attendees:
                # Auto-group ONLY the unassigned players into the remaining spots
                # This part is complex: need to know remaining spots per court.
                # SIMPLER MERGE: Calculate auto for everyone, then overwrite.
                auto_assignments = _calculate_skill_priority_groups(current_attendees, num_courts)
                base_assignments_for_block = defaultdict(list) # Reset
                for court_num in range(1, num_courts + 1):
                    base_assignments_for_block[court_num] = list(auto_assignments.get(court_num, []))

                # Merge manual over auto
                for court_num in range(1, num_courts + 1):
                    current_court_list = base_assignments_for_block[court_num]
                    base_assignments_for_block[court_num] = [
                        p for p in current_court_list if p not in manually_assigned_players
                    ]
                for player, target_court in manual_assignments_map.items():
                    if player not in base_assignments_for_block[target_court]:
                         base_assignments_for_block[target_court].append(player)

        elif current_attendees.exists() and num_courts > 0:
             # Fallback to automatic if no manual assignments found
             base_assignments_for_block = _calculate_skill_priority_groups(current_attendees, num_courts)
        # Else: base_assignments_for_block remains empty defaultdict

        # Ensure all courts exist and sort
        final_base_assignments = {}
        for court_idx in range(1, num_courts + 1):
            player_list = base_assignments_for_block.get(court_idx, [])
            player_list.sort(key=lambda p: (p.last_name, p.first_name))
            final_base_assignments[court_idx] = player_list
        # --- End Determine Base Assignments ---

        current_display_assignments = final_base_assignments # Start with merged base/manual
        is_current = False

        if block_start_dt and block_end_dt and block_start_dt <= effective_time < block_end_dt:
            is_current = True
            if interval and interval > 0 and final_base_assignments and num_courts > 0:
                minutes_into_block = 0.0
                rotation_cycle = 0
                next_rotation_dt_utc = None

                if effective_time >= block_start_dt:
                    try:
                        if timezone.is_aware(effective_time) and timezone.is_aware(block_start_dt):
                             minutes_into_block = (effective_time - block_start_dt).total_seconds() / 60.0
                    except TypeError:
                        minutes_into_block = 0.0

                try:
                    if minutes_into_block >= 0 and interval > 0:
                        rotation_cycle = math.floor(minutes_into_block / float(interval))
                    else:
                        rotation_cycle = 0
                except (TypeError, ValueError):
                    rotation_cycle = 0

                if interval > 0:
                    try:
                        next_rotation_offset_minutes = (rotation_cycle + 1) * float(interval)
                        potential_next_rotation_dt = block_start_dt + datetime.timedelta(minutes=next_rotation_offset_minutes)
                        if potential_next_rotation_dt < block_end_dt:
                            next_rotation_dt_utc = potential_next_rotation_dt
                            next_rotation_time_iso = next_rotation_dt_utc.isoformat()
                            display_next_rotation_time = timezone.localtime(next_rotation_dt_utc)
                    except (TypeError, ValueError):
                        pass

                # Apply rotation for display (operates on final_base_assignments)
                if rotation_cycle > 0:
                    rotated_assignments_temp = {}
                    initial_group_keys = sorted(list(final_base_assignments.keys()))
                    num_initial_groups = len(initial_group_keys)
                    if num_initial_groups > 0:
                        for court_num_target in range(1, num_courts + 1):
                            if court_num_target in initial_group_keys:
                                original_court_index = (((court_num_target - 1) - rotation_cycle) % num_courts) % num_initial_groups
                                original_group_key = initial_group_keys[original_court_index]
                                rotated_assignments_temp[court_num_target] = final_base_assignments.get(original_group_key, [])
                            else:
                                rotated_assignments_temp[court_num_target] = []
                        current_display_assignments = rotated_assignments_temp # Overwrite with rotated

        # Prepare block_info using the final current_display_assignments
        block_info = {
            'block': block,
            'assignments': current_display_assignments, # This now holds rotated manual/auto groups
            'start_dt': block_start_dt,
            'end_dt': block_end_dt,
            'block_activities': block_activities
        }
        processed_block_data.append(block_info)

        if is_current:
            current_block_data = block_info
        elif not current_block_data and block_start_dt and block_start_dt > effective_time:
             if next_block_data is None:
                 # For next block display, show the BASE assignments (manual or auto), not rotated ones
                 next_block_info = {
                     'block': block, 'assignments': final_base_assignments,
                     'start_dt': block_start_dt, 'end_dt': block_end_dt,
                     'block_activities': block_activities
                 }
                 next_block_data = next_block_info

    if not current_block_data and not next_block_data and processed_block_data:
         # If session hasn't started, show first block as 'next' using its base assignments
         first_block = processed_block_data[0]['block']
         first_block_assignments = {} # Recalculate base for first block
         manual_assignments_qs_first = ManualCourtAssignment.objects.filter(time_block=first_block, player__in=current_attendees_set).select_related('player')
         if manual_assignments_qs_first.exists():
              # Build from manual
              temp_assignments = defaultdict(list)
              for ma in manual_assignments_qs_first: temp_assignments[ma.court_number].append(ma.player)
              for court_idx in range(1, first_block.number_of_courts + 1): first_block_assignments[court_idx] = sorted(temp_assignments.get(court_idx, []), key=lambda p: (p.last_name, p.first_name))
         elif current_attendees.exists() and first_block.number_of_courts > 0:
              # Build from auto
              first_block_assignments = _calculate_skill_priority_groups(current_attendees, first_block.number_of_courts)
         processed_block_data[0]['assignments'] = first_block_assignments # Update assignments in processed data
         next_block_data = processed_block_data[0]


    context = {
        'session': session,
        'current_block_data': current_block_data,
        'next_block_data': next_block_data,
        'display_effective_time': local_effective_time,
        'effective_time_iso': effective_time.isoformat(),
        'is_simulated': is_simulated,
        'sim_time_input_value': sim_time_input_value,
        'next_rotation_time_iso': next_rotation_time_iso,
        'display_next_rotation_time': display_next_rotation_time
    }
    return render(request, 'planning/live_session.html', context)


# --- Add/Edit/Delete Activity Views ---
def add_activity(request, block_id, court_num):
    block = get_object_or_404(TimeBlock, pk=block_id)
    session = block.session
    form = ActivityAssignmentForm()

    if request.method == 'POST':
        form = ActivityAssignmentForm(request.POST)
        if form.is_valid():
            submitted_duration = form.cleaned_data.get('duration_minutes') or 0
            existing_activities = ActivityAssignment.objects.filter(
                time_block=block, court_number=court_num
            )
            total_existing_duration = sum(act.duration_minutes for act in existing_activities)
            new_total_duration = total_existing_duration + submitted_duration
            if new_total_duration > block.duration_minutes:
                form.add_error(
                    None,
                    f"Adding activity ({submitted_duration}m) exceeds block duration "
                    f"({block.duration_minutes}m) for Court {court_num}. "
                    f"Used: {total_existing_duration}m."
                )
            else:
                new_activity = form.save(commit=False)
                new_activity.time_block = block
                new_activity.court_number = court_num
                new_activity.save()
                return redirect('planning:session_detail', session_id=block.session.id)

    context = {
        'form': form,
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
    form = ActivityAssignmentForm(instance=activity_to_edit)

    if request.method == 'POST':
        form = ActivityAssignmentForm(request.POST, instance=activity_to_edit)
        if form.is_valid():
            submitted_duration = form.cleaned_data.get('duration_minutes') or 0
            existing_activities = ActivityAssignment.objects.filter(
                time_block=block, court_number=court_num
            ).exclude(pk=activity_id)
            total_existing_duration = sum(act.duration_minutes for act in existing_activities)
            new_total_duration = total_existing_duration + submitted_duration
            if new_total_duration > block.duration_minutes:
                 form.add_error(
                     None,
                     f"Saving activity ({submitted_duration}m) exceeds block duration "
                     f"({block.duration_minutes}m) for Court {court_num}. "
                     f"Others: {total_existing_duration}m."
                 )
            else:
                form.save()
                return redirect('planning:session_detail', session_id=session.id)

    context = {
        'form': form,
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

    context = {
        'activity': activity_to_delete,
        'session_id': session_id
    }
    return render(request, 'planning/delete_activity_confirm.html', context)


# --- Player Profile View ---
def player_profile(request, player_id):
    player = get_object_or_404(Player.objects.prefetch_related('school_groups'), pk=player_id) # Prefetch groups

    # --- Attendance Calculation ---
    sessions_attended_qs = player.attended_sessions.filter(
        session_date__lte=timezone.now().date() # Only count past/present attended sessions
    ).order_by('-session_date', '-session_start_time')
    attended_sessions_count = sessions_attended_qs.count()

    player_group_ids = player.school_groups.values_list('id', flat=True)
    total_relevant_sessions_count = 0
    attendance_percentage = None

    if player_group_ids:
        total_relevant_sessions_count = Session.objects.filter(
            school_group_id__in=player_group_ids,
            session_date__lte=timezone.now().date() # Count only past/present sessions for the groups
        ).count()

        if total_relevant_sessions_count > 0:
            attendance_percentage = round((attended_sessions_count / total_relevant_sessions_count) * 100)
        elif attended_sessions_count == 0:
             # If no relevant sessions held, but somehow attended 0? Percentage is N/A or 100%? Let's say N/A.
             attendance_percentage = None # Or consider 100% if 0/0 is desired
        # Handle case where attended > total (shouldn't happen with correct logic)

    # --- End Attendance Calculation ---


    # Fetch other related data
    assessments = player.session_assessments.select_related(
        'session', 'session__school_group'
    ).order_by('-date_recorded', '-session__session_start_time')
    sprints = player.sprint_records.select_related('session').order_by('date_recorded')
    volleys = player.volley_records.select_related('session').order_by('date_recorded')
    drives = player.drive_records.select_related('session').order_by('date_recorded')
    matches = player.match_results.select_related('session').order_by('-date')

    # Chart data preparation...
    sprint_chart_data = { '3m': {'labels': [], 'data': []}, '5m': {'labels': [], 'data': []}, '10m': {'labels': [], 'data': []} }
    for sprint in sprints:
        key = sprint.duration_choice
        if key in sprint_chart_data:
            sprint_chart_data[key]['labels'].append(sprint.date_recorded.isoformat())
            sprint_chart_data[key]['data'].append(sprint.score)

    volley_chart_data = { 'FH': {'labels': [], 'data': []}, 'BH': {'labels': [], 'data': []} }
    for volley in volleys:
        key = volley.shot_type
        if key in volley_chart_data:
            volley_chart_data[key]['labels'].append(volley.date_recorded.isoformat())
            volley_chart_data[key]['data'].append(volley.consecutive_count)

    drive_chart_data = { 'FH': {'labels': [], 'data': []}, 'BH': {'labels': [], 'data': []} }
    for drive in drives:
        key = drive.shot_type
        if key in drive_chart_data:
            drive_chart_data[key]['labels'].append(drive.date_recorded.isoformat())
            drive_chart_data[key]['data'].append(drive.consecutive_count)

    context = {
        'player': player,
        'sessions_attended': sessions_attended_qs, # Pass the queryset
        'attended_sessions_count': attended_sessions_count, # Pass the count
        'total_relevant_sessions_count': total_relevant_sessions_count, # Pass total count
        'attendance_percentage': attendance_percentage, # Pass the calculated percentage
        'assessments': assessments,
        'sprints': sprints,
        'volleys': volleys,
        'drives': drives,
        'matches': matches,
        'sprint_chart_data': sprint_chart_data, # Pass dict directly
        'volley_chart_data': volley_chart_data, # Pass dict directly
        'drive_chart_data': drive_chart_data, # Pass dict directly
    }
    return render(request, 'planning/player_profile.html', context)

    context = {
        'player': player,
        'sessions_attended': sessions_attended,
        'assessments': assessments,
        'sprints': sprints,
        'volleys': volleys,
        'drives': drives,
        'matches': matches,
        # CORRECTED: Pass Python dictionaries directly to context
        'sprint_chart_data': sprint_chart_data,
        'volley_chart_data': volley_chart_data,
        'drive_chart_data': drive_chart_data,
    }
    return render(request, 'planning/player_profile.html', context)


# --- Assess Player Session View ---
# (Keep existing assess_player_session view code as corrected previously)
def assess_player_session(request, session_id, player_id):
    session = get_object_or_404(Session, pk=session_id)
    player = get_object_or_404(Player, pk=player_id)
    assessment_instance = SessionAssessment.objects.filter(session=session, player=player).first()

    if request.method == 'POST':
        form = SessionAssessmentForm(request.POST, instance=assessment_instance)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.session = session
            assessment.player = player
            if not assessment.pk and not form.cleaned_data.get('date_recorded'):
                 assessment.date_recorded = session.session_date
            assessment.save()
            messages.success(request, f"Assessment saved for {player.full_name} in session on {session.session_date}.")
            return redirect('planning:pending_assessments')
    else:
        form = SessionAssessmentForm(instance=assessment_instance)

    context = {
        'form': form,
        'session': session,
        'player': player,
        'assessment_instance': assessment_instance,
        'page_title': f"{'Edit' if assessment_instance else 'Add'} Assessment"
    }
    return render(request, 'planning/assess_player_form.html', context)


# Add this view for handling Coach Feedback form
def add_coach_feedback(request, player_id):
    """
    View to add structured coach feedback for a specific player.
    """
    player = get_object_or_404(Player, pk=player_id)

    if request.method == 'POST':
        # Pass player instance if form's __init__ needs it for filtering sessions
        # form = CoachFeedbackForm(request.POST, player=player) 
        form = CoachFeedbackForm(request.POST) # Use this if not filtering sessions in form
        if form.is_valid():
            feedback = form.save(commit=False) # Don't save to DB yet
            feedback.player = player # Assign the correct player
            # TODO: Assign feedback.recorded_by = request.user (or logged-in coach) if auth is implemented
            feedback.save() # Save the complete feedback entry to DB
            # Optionally add a success message using django.contrib.messages
            # messages.success(request, f"Feedback added for {player.full_name}.")
            return redirect('planning:player_profile', player_id=player.id) # Redirect back to player profile
    else: # GET request
        # Pass player instance if form's __init__ needs it for filtering sessions
        # form = CoachFeedbackForm(player=player) 
        form = CoachFeedbackForm() # Use this if not filtering sessions in form

    context = {
        'form': form,
        'player': player,
        'page_title': f'Add Feedback for {player.full_name}'
    }
    # We need to create this template file next ('add_coach_feedback_form.html')
    return render(request, 'planning/add_coach_feedback_form.html', context)


# --- Session Assessment View ---
def assess_player_session(request, session_id, player_id):
    session = get_object_or_404(Session, pk=session_id)
    player = get_object_or_404(Player, pk=player_id)
    # Try to get an existing assessment or create a new one
    assessment_instance = SessionAssessment.objects.filter(session=session, player=player).first()

    if request.method == 'POST':
        form = SessionAssessmentForm(request.POST, instance=assessment_instance)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.session = session
            assessment.player = player
            # Ensure date is set if creating new (form might handle this)
            # If date_recorded is not part of the form, set it from the session's date
            if not assessment.pk and not form.cleaned_data.get('date_recorded'): # Check if form includes date_recorded
                 # CORRECTED: Use session.session_date
                 assessment.date_recorded = session.session_date
            assessment.save()
            messages.success(request, f"Assessment saved for {player.full_name} in session on {session.session_date}.")
            # Redirect back to pending assessments page after saving
            return redirect('planning:pending_assessments') # Changed redirect
    else: # GET request
        form = SessionAssessmentForm(instance=assessment_instance)

    context = {
        'form': form,
        'session': session,
        'player': player,
        'assessment_instance': assessment_instance, # Pass instance to template
        'page_title': f"{'Edit' if assessment_instance else 'Add'} Assessment" # Dynamic title
    }
    return render(request, 'planning/assess_player_form.html', context)

def assess_latest_session_redirect(request, player_id):
    """
    Finds the most recent session the player attended and redirects
    to the assessment form for that session and player.
    """
    player = get_object_or_404(Player, pk=player_id)

    # Find the latest session this player attended
    # Uses the 'attended_sessions' related name from Session.attendees M2M
    latest_session = player.attended_sessions.order_by('-session_date', '-session_start_time').first()

    if latest_session:
        # Redirect to the existing assessment view, passing both IDs
        return redirect('planning:assess_player_session', session_id=latest_session.id, player_id=player.id)
    else:
        # Handle case where player hasn't attended any sessions
        messages.warning(request, f"{player.full_name} has no recorded session attendance to assess.")
        # Redirect back to the player's profile page
        return redirect('planning:player_profile', player_id=player.id)


def pending_assessments_view(request):
    """
    Displays sessions needing assessment and handles marking them complete.
    """
    if request.method == 'POST':
        # Handle marking sessions as complete
        session_ids_to_complete = request.POST.getlist('sessions_to_complete')
        if session_ids_to_complete:
            sessions_updated = Session.objects.filter(
                id__in=session_ids_to_complete,
                assessments_complete=False # Only update those not already marked
            ).update(assessments_complete=True)

            if sessions_updated > 0:
                messages.success(request, f"{sessions_updated} session(s) marked as assessment complete.")
            else:
                messages.info(request, "No sessions were updated (they might have already been marked complete).")
        else:
            messages.warning(request, "No sessions selected to mark as complete.")

        # Redirect back to the same page to show updated list
        return redirect('planning:pending_assessments')

    # --- Handle GET request ---
    # Calculate the date 14 days ago
    two_weeks_ago = timezone.now().date() - timedelta(days=14)

    # Fetch sessions within the last 14 days that are NOT marked complete
    # Prefetch attendees for efficiency
    pending_sessions_qs = Session.objects.filter(
        session_date__gte=two_weeks_ago,
        assessments_complete=False
    ).select_related('school_group').prefetch_related(
        Prefetch('attendees', queryset=Player.objects.order_by('last_name', 'first_name'))
    ).order_by('-session_date', '-session_start_time') # Show most recent first

    # Group sessions by date for display
    grouped_sessions = defaultdict(list)
    for session in pending_sessions_qs:
        grouped_sessions[session.session_date].append(session)

    context = {
        'grouped_pending_sessions': dict(grouped_sessions), # Convert back to dict for template
        'page_title': "Pending Assessments"
    }
    # We will create this template in the next step
    return render(request, 'planning/pending_assessments.html', context)


# --- Add Metric/Match Views ---
def add_sprint_record(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    form = CourtSprintRecordForm()
    if request.method == 'POST':
        form = CourtSprintRecordForm(request.POST)
        if form.is_valid():
            sprint_record = form.save(commit=False)
            sprint_record.player = player
            sprint_record.save()
            return redirect('planning:player_profile', player_id=player.id)

    context = {
        'form': form,
        'player': player
    }
    return render(request, 'planning/add_sprint_form.html', context)

def add_volley_record(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    form = VolleyRecordForm()
    if request.method == 'POST':
        form = VolleyRecordForm(request.POST)
        if form.is_valid():
            volley_record = form.save(commit=False)
            volley_record.player = player
            volley_record.save()
            return redirect('planning:player_profile', player_id=player.id)

    context = {
        'form': form,
        'player': player
    }
    return render(request, 'planning/add_volley_form.html', context)

def add_drive_record(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    form = BackwallDriveRecordForm()
    if request.method == 'POST':
        form = BackwallDriveRecordForm(request.POST)
        if form.is_valid():
            drive_record = form.save(commit=False)
            drive_record.player = player
            drive_record.save()
            return redirect('planning:player_profile', player_id=player.id)

    context = {
        'form': form,
        'player': player
    }
    return render(request, 'planning/add_drive_form.html', context)

def add_match_result(request, player_id):
    player = get_object_or_404(Player, pk=player_id)
    form = MatchResultForm()
    if request.method == 'POST':
        form = MatchResultForm(request.POST)
        if form.is_valid():
            match_result = form.save(commit=False)
            match_result.player = player
            match_result.save()
            return redirect('planning:player_profile', player_id=player.id)

    context = {
        'form': form,
        'player': player
    }
    return render(request, 'planning/add_match_form.html', context)


# --- One-Page Plan View ---
# NOTE: This view needs modification to show manual assignments if they exist
def one_page_plan_view(request, session_id):
    """Displays a simplified, shareable view of the session plan."""
    session = get_object_or_404(Session, pk=session_id)
    time_blocks = session.time_blocks.all().order_by('start_offset_minutes')
    activities = ActivityAssignment.objects.filter(
        time_block__session=session
    ).select_related('drill', 'lead_coach').order_by(
        'time_block__start_offset_minutes', 'court_number', 'order'
    )
    coaches = session.coaches_attending.all()

    # TODO: Add logic here similar to session_detail/live_session
    # to fetch manual assignments per block and pass them to the template
    # For now, it only shows activities.

    context = {
        'session': session,
        'time_blocks': time_blocks,
        'activities': activities,
        'coaches': coaches,
    }
    return render(request, 'planning/one_page_plan.html', context)

# planning/views.py

# --- Homepage View ---
def homepage_view(request):
    """
    Displays the main homepage / dashboard.
    Includes upcoming sessions and recently completed sessions for feedback reminders.
    """
    now = timezone.now()

    # --- Upcoming Sessions (Using CORRECTED field names) ---
    upcoming_sessions = Session.objects.filter(
        Q(session_date__gt=now.date()) | Q(session_date=now.date(), session_start_time__gte=now.time())
    ).select_related('school_group').order_by('session_date', 'session_start_time')[:5] # Use session_date, session_start_time

    # --- Recently Finished Sessions for Feedback Reminder (Updated Window & Filtered) ---
    feedback_window_start = now - timedelta(days=14)
    fifteen_days_ago = now.date() - timedelta(days=15)

    potential_sessions = Session.objects.filter(
        session_date__gte=fifteen_days_ago,
        session_date__lte=now.date(),
        assessments_complete=False # <-- ADDED: Only show if not marked complete
    ).select_related('school_group').order_by('-session_date', '-session_start_time')

    # Iterate in Python and check the calculated end_datetime property
    recent_sessions_for_feedback = []
    for session in potential_sessions:
        # Check if the session has an end time calculated
        if session.end_datetime:
            # Check if the end time falls within our desired window (past 14 days, but before now)
            # Note: The assessments_complete=False filter is already applied in the DB query
            if feedback_window_start <= session.end_datetime < now:
                recent_sessions_for_feedback.append(session)

        # Limit the list
        if len(recent_sessions_for_feedback) >= 5:
            break
    # --- End Recently Finished Sessions ---

    context = {
        'upcoming_sessions': upcoming_sessions,
        'recent_sessions_for_feedback': recent_sessions_for_feedback, # Pass updated list to context
    }
    return render(request, 'planning/homepage.html', context)
 
    # --- End Recently Finished Sessions ---

    context = {
        'upcoming_sessions': upcoming_sessions,
        'recent_sessions_for_feedback': recent_sessions_for_feedback, # Add new list to context
    }
    return render(request, 'planning/homepage.html', context)

# --- API View for Manual Assignments ---
@require_POST
# @csrf_exempt # REMEMBER TO REMOVE THIS once CSRF token is sent from JS
def update_manual_assignment_api(request):
    """API endpoint to save manual player-court assignments."""
    try:
        data = json.loads(request.body)
        player_id = data.get('player_id')
        time_block_id = data.get('time_block_id')
        court_number = data.get('court_number')

        if not all([player_id, time_block_id, court_number]):
            return JsonResponse({'status': 'error', 'message': 'Missing data'}, status=400)

        try:
            player = Player.objects.get(pk=int(player_id))
            time_block = TimeBlock.objects.get(pk=int(time_block_id))
            court_num_int = int(court_number)
            if court_num_int <= 0 or court_num_int > time_block.number_of_courts:
                 return JsonResponse({'status': 'error', 'message': 'Invalid court number for this block'}, status=400)

        except (Player.DoesNotExist, TimeBlock.DoesNotExist, ValueError):
            return JsonResponse({'status': 'error', 'message': 'Invalid player, block, or court ID'}, status=400)

        assignment, created = ManualCourtAssignment.objects.update_or_create(
            time_block=time_block,
            player=player,
            defaults={'court_number': court_num_int}
        )

        message = f'Assignment {"created" if created else "updated"} for {player.full_name}.'
        return JsonResponse({
            'status': 'success',
            'message': message,
            'player_id': player_id,
            'time_block_id': time_block_id,
            'new_court': court_num_int
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in update_manual_assignment_api: {e}") # Basic logging
        return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred'}, status=500)

# --- API View for Clearing Manual Assignments ---
@require_POST
def clear_manual_assignments_api(request, time_block_id):
    """API endpoint to delete all manual assignments for a specific time block."""
    try:
        time_block = get_object_or_404(TimeBlock, pk=time_block_id)
        # Delete all manual assignments associated with this time block
        deleted_count, _ = ManualCourtAssignment.objects.filter(time_block=time_block).delete()

        return JsonResponse({
            'status': 'success',
            'message': f'Cleared {deleted_count} manual assignment(s) for this block. Automatic grouping will now apply.',
            'time_block_id': time_block_id
        })
    except Http404:
         return JsonResponse({'status': 'error', 'message': 'Time block not found.'}, status=404)
    except Exception as e:
        print(f"Error in clear_manual_assignments_api: {e}") # Basic logging
        return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred'}, status=500)

def pending_assessments_view(request):
    """
    Displays sessions needing assessment and handles marking them complete.
    """
    if request.method == 'POST':
        # Handle marking sessions as complete
        session_ids_to_complete = request.POST.getlist('sessions_to_complete')
        if session_ids_to_complete:
            sessions_updated = Session.objects.filter(
                id__in=session_ids_to_complete,
                assessments_complete=False # Only update those not already marked
            ).update(assessments_complete=True)

            if sessions_updated > 0:
                messages.success(request, f"{sessions_updated} session(s) marked as assessment complete.")
            else:
                messages.info(request, "No sessions were updated (they might have already been marked complete).")
        else:
            messages.warning(request, "No sessions selected to mark as complete.")

        # Redirect back to the same page to show updated list
        return redirect('planning:pending_assessments')

    # --- Handle GET request ---
    # Calculate the date 14 days ago
    two_weeks_ago = timezone.now().date() - timedelta(days=14)

    # Fetch sessions within the last 14 days that are NOT marked complete
    # Prefetch attendees for efficiency
    pending_sessions_qs = Session.objects.filter(
        session_date__gte=two_weeks_ago,
        assessments_complete=False
    ).select_related('school_group').prefetch_related(
        Prefetch('attendees', queryset=Player.objects.order_by('last_name', 'first_name'))
    ).order_by('-session_date', '-session_start_time') # Show most recent first

    # Group sessions by date for display
    grouped_sessions = defaultdict(list)
    for session in pending_sessions_qs:
        grouped_sessions[session.session_date].append(session)

    context = {
        'grouped_pending_sessions': dict(grouped_sessions), # Convert back to dict for template
        'page_title': "Pending Assessments"
    }
    # We will create this template in the next step
    return render(request, 'planning/pending_assessments.html', context)

# End of file
