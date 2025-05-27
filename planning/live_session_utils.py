# planning/live_session_utils.py

from django.utils import timezone
from django.db.models import Prefetch # Retained if you use it elsewhere or plan to optimize session query later
from datetime import timedelta, datetime as dt_class # Ensure datetime is imported as dt_class
from collections import defaultdict
from math import floor # Added for floor division

# Import necessary models from the planning app
from planning.models import Session, TimeBlock, ActivityAssignment, ManualCourtAssignment, Player, SchoolGroup 
# Assuming Drill model is also part of planning.models if used by ActivityAssignment
import pprint # For debugging

# --- Helper function for skill-based player grouping ---
def _calculate_skill_priority_groups(players, num_courts):
    """
    Sorts players by skill level (Advanced, Intermediate, Beginner) and then by name,
    and distributes them as evenly as possible across the available courts.
    """
    skill_order = {
        Player.SkillLevel.ADVANCED: 0, 
        Player.SkillLevel.INTERMEDIATE: 1, 
        Player.SkillLevel.BEGINNER: 2
    }
    if not players:
        return {}

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


def get_session_live_state(session_obj, effective_current_time):
    session = session_obj
    if timezone.is_naive(effective_current_time):
        effective_current_time = timezone.make_aware(effective_current_time, timezone.get_current_timezone())
    
    session_start_dt = session.start_datetime 
    session_end_dt = session.end_datetime

    if not session_start_dt or not session_end_dt:
        return {'session_info': {'status_message': 'Session start/end time not properly defined.'}}

    live_state = {
        'session_info': {
            'id': session.id,
            'name_display': f"{session.school_group.name if session.school_group else 'Session'} - {session.session_date.strftime('%d %b %Y')}",
            'overall_start_datetime_iso': session_start_dt.isoformat(),
            'overall_end_datetime_iso': session_end_dt.isoformat(),
            'is_live': False,
            'status_message': "Loading...", # Neutral default
            'attending_players_names': [] 
        },
        'current_time_block': None, 'next_time_block_preview': None, 'courts_data': [], 
        'is_rotation_alert_active': False, 'effective_current_time_iso': effective_current_time.isoformat(),
    }

    # Determine session phase first
    if effective_current_time < session_start_dt:
        live_state['session_info']['is_live'] = False
        time_to_start = session_start_dt - effective_current_time
        minutes_to_start = int(time_to_start.total_seconds() // 60)
        if minutes_to_start >= 60:
            hours_to_start = minutes_to_start // 60
            remaining_minutes = minutes_to_start % 60
            live_state['session_info']['status_message'] = f"Session starts in {hours_to_start}h {remaining_minutes}m"
        elif minutes_to_start > 0:
            live_state['session_info']['status_message'] = f"Session starts in {minutes_to_start} minutes"
        else:
            live_state['session_info']['status_message'] = "Session starting now!"
        attendees = session.attendees.all().order_by('first_name', 'last_name')
        live_state['session_info']['attending_players_names'] = [player.first_name for player in attendees]
        pprint.pprint(live_state)
        return live_state
        
    elif effective_current_time >= session_end_dt:
        live_state['session_info']['is_live'] = False
        live_state['session_info']['status_message'] = "Session Finished!" # More concise
        pprint.pprint(live_state)
        return live_state
    
    else: # Session is In Progress
        live_state['session_info']['is_live'] = True
        live_state['session_info']['status_message'] = "Session In Progress" 

    # --- In Progress Logic ---
    current_block_obj = None
    block_start_absolute = None 
    ordered_blocks = list(session.time_blocks.order_by('start_offset_minutes'))

    for i, block in enumerate(ordered_blocks):
        current_block_start_absolute_dt = session_start_dt + timedelta(minutes=block.start_offset_minutes)
        current_block_end_absolute_dt = current_block_start_absolute_dt + timedelta(minutes=block.duration_minutes)
        if current_block_start_absolute_dt <= effective_current_time < current_block_end_absolute_dt:
            current_block_obj = block
            block_start_absolute = current_block_start_absolute_dt 
            live_state['current_time_block'] = {
                'id': block.id, 'block_focus': block.block_focus or "Activity", # Shorter default
                'block_start_datetime_iso': current_block_start_absolute_dt.isoformat(),
                'block_end_datetime_iso': current_block_end_absolute_dt.isoformat(),
                'time_remaining_in_block_seconds': int((current_block_end_absolute_dt - effective_current_time).total_seconds()),
                'rotation_interval_minutes': block.rotation_interval_minutes,
                'next_rotation_due_datetime_iso': None 
            }
            if (i + 1) < len(ordered_blocks):
                next_b = ordered_blocks[i+1]
                live_state['next_time_block_preview'] = {
                    'block_focus': next_b.block_focus or "Next Activity",
                    'starts_in_seconds': int(((session_start_dt + timedelta(minutes=next_b.start_offset_minutes)) - effective_current_time).total_seconds())
                }
            break 
        elif effective_current_time < current_block_start_absolute_dt and not live_state['current_time_block']:
            live_state['session_info']['status_message'] = f"Next: {block.block_focus or 'Activity'}"
            live_state['next_time_block_preview'] = {
                'block_focus': block.block_focus or "Next Activity",
                'starts_in_seconds': int((current_block_start_absolute_dt - effective_current_time).total_seconds())}
            break 

    if not current_block_obj: 
        if live_state['session_info']['is_live'] and not live_state['next_time_block_preview']:
             live_state['session_info']['status_message'] = "Session active, no current block."
        pprint.pprint(live_state)
        return live_state 
    
    # Base status for active block, can be overridden by rotation alert
    live_state['session_info']['status_message'] = f"{current_block_obj.block_focus or 'Activity'}"

    time_into_block_seconds_overall = (effective_current_time - block_start_absolute).total_seconds()
    rotation_interval_seconds_for_block = current_block_obj.rotation_interval_minutes * 60 if current_block_obj.rotation_interval_minutes else 0

    if rotation_interval_seconds_for_block > 0:
        rotations_passed = floor(time_into_block_seconds_overall / rotation_interval_seconds_for_block)
        next_rotation_offset_seconds = (rotations_passed + 1) * rotation_interval_seconds_for_block
        next_rotation_dt = block_start_absolute + timedelta(seconds=next_rotation_offset_seconds)
        current_block_actual_end_dt = block_start_absolute + timedelta(minutes=current_block_obj.duration_minutes)
        if next_rotation_dt < current_block_actual_end_dt: 
            if live_state['current_time_block']:
                 live_state['current_time_block']['next_rotation_due_datetime_iso'] = next_rotation_dt.isoformat()
            time_until_next_rotation_seconds = (next_rotation_dt - effective_current_time).total_seconds()
            if (-5 < time_until_next_rotation_seconds < 10): 
                live_state['is_rotation_alert_active'] = True
                live_state['session_info']['status_message'] = "ROTATE NOW!" 

    # Player Assignment Logic (remains the same)
    # ...
    display_attendees = list(session.attendees.all())
    manual_assignments_for_block = ManualCourtAssignment.objects.filter(
        time_block=current_block_obj, player__in=display_attendees
    ).select_related('player')
    manual_map_for_block = {ma.player_id: ma.court_number for ma in manual_assignments_for_block}
    manually_assigned_player_ids_for_block = set(manual_map_for_block.keys())
    players_for_auto_grouping = [p for p in display_attendees if p.id not in manually_assigned_player_ids_for_block]
    auto_assignments = _calculate_skill_priority_groups(players_for_auto_grouping, current_block_obj.number_of_courts)
    initial_assignments_this_block = defaultdict(list)
    for court_idx in range(1, current_block_obj.number_of_courts + 1): 
        initial_assignments_this_block[court_idx].extend(auto_assignments.get(court_idx, []))
    for player_id, target_court_num in manual_map_for_block.items():
        player_obj = next((p for p in display_attendees if p.id == player_id), None)
        if player_obj:
            for auto_court_num, auto_players in list(initial_assignments_this_block.items()):
                if auto_court_num != target_court_num and player_obj in auto_players:
                    initial_assignments_this_block[auto_court_num].remove(player_obj)
            if player_obj not in initial_assignments_this_block[target_court_num]:
                initial_assignments_this_block[target_court_num].append(player_obj)
    for court_idx_sort in initial_assignments_this_block: 
        initial_assignments_this_block[court_idx_sort].sort(key=lambda p: (p.last_name, p.first_name))

    final_court_assignments_for_block = initial_assignments_this_block 
    num_rotations_occurred = 0
    if rotation_interval_seconds_for_block > 0 and time_into_block_seconds_overall >= rotation_interval_seconds_for_block:
        num_rotations_occurred = floor(time_into_block_seconds_overall / rotation_interval_seconds_for_block)
    if num_rotations_occurred > 0 and current_block_obj.number_of_courts > 1:
        current_assignments_to_rotate = defaultdict(list)
        for court_k_copy, players_list in initial_assignments_this_block.items():
            current_assignments_to_rotate[court_k_copy].extend(players_list)
        for _ in range(num_rotations_occurred): 
            single_step_rotated_assignments = defaultdict(list)
            num_courts_val = current_block_obj.number_of_courts 
            for i_court in range(1, num_courts_val + 1):
                players_on_this_court = current_assignments_to_rotate[i_court] 
                target_court_num_after_one_rotation = (i_court % num_courts_val) + 1 
                single_step_rotated_assignments[target_court_num_after_one_rotation].extend(players_on_this_court)
            current_assignments_to_rotate = single_step_rotated_assignments 
        final_court_assignments_for_block = current_assignments_to_rotate 
        for court_idx_sort_final in final_court_assignments_for_block:
            final_court_assignments_for_block[court_idx_sort_final].sort(key=lambda p: (p.last_name, p.first_name))


    # Court Activity Calculation Logic (remains the same)
    # ...
    activities_qs = current_block_obj.activities.select_related('drill').order_by('court_number', 'order')
    all_activities_for_current_block = list(activities_qs)
    live_state['courts_data'] = [] 
    for court_num_loop in range(1, current_block_obj.number_of_courts + 1):
        court_activities_sequence = [act for act in all_activities_for_current_block if act.court_number == court_num_loop]
        current_activity_details = None
        next_activity_in_sequence_details = None
        if not court_activities_sequence:
            live_state['courts_data'].append({
                'court_number': court_num_loop,
                'current_activity': None,
                'next_activity_in_block': None, 
                'assigned_players': [p.full_name for p in final_court_assignments_for_block.get(court_num_loop, [])]
            })
            continue
        effective_time_within_activity_cycle = 0
        if rotation_interval_seconds_for_block > 0:
            effective_time_within_activity_cycle = time_into_block_seconds_overall % rotation_interval_seconds_for_block
        else:
            effective_time_within_activity_cycle = time_into_block_seconds_overall
        cumulative_duration_in_cycle_seconds = 0
        found_current_activity_for_this_court = False
        for i_act_loop, activity_assignment in enumerate(court_activities_sequence):
            activity_duration_minutes = activity_assignment.duration_minutes if activity_assignment.duration_minutes is not None else 0
            activity_duration_seconds = activity_duration_minutes * 60
            activity_slot_start_in_cycle = cumulative_duration_in_cycle_seconds
            activity_slot_end_in_cycle = cumulative_duration_in_cycle_seconds + activity_duration_seconds
            if not found_current_activity_for_this_court and \
               activity_slot_start_in_cycle <= effective_time_within_activity_cycle < activity_slot_end_in_cycle:
                time_until_natural_end_of_this_activity_instance = activity_slot_end_in_cycle - effective_time_within_activity_cycle
                time_remaining_for_display_on_timer = time_until_natural_end_of_this_activity_instance
                if rotation_interval_seconds_for_block > 0:
                    time_remaining_in_current_rotation_segment = rotation_interval_seconds_for_block - effective_time_within_activity_cycle
                    time_remaining_for_display_on_timer = min(time_until_natural_end_of_this_activity_instance, time_remaining_in_current_rotation_segment)
                current_activity_details = {
                    'name': activity_assignment.drill.name if activity_assignment.drill else activity_assignment.custom_activity_name,
                    'activity_id': activity_assignment.id, 
                    'time_remaining_in_activity_seconds': int(max(0, time_remaining_for_display_on_timer))
                }
                found_current_activity_for_this_court = True
                if (i_act_loop + 1) < len(court_activities_sequence):
                    next_aa_in_seq = court_activities_sequence[i_act_loop + 1]
                    next_activity_in_sequence_details = {
                        'name': next_aa_in_seq.drill.name if next_aa_in_seq.drill else next_aa_in_seq.custom_activity_name,
                        'duration_minutes': next_aa_in_seq.duration_minutes
                    }
                elif rotation_interval_seconds_for_block > 0 and court_activities_sequence: 
                    first_aa_in_seq = court_activities_sequence[0]
                    next_activity_in_sequence_details = { 
                        'name': first_aa_in_seq.drill.name if first_aa_in_seq.drill else first_aa_in_seq.custom_activity_name,
                        'duration_minutes': first_aa_in_seq.duration_minutes
                    }
            cumulative_duration_in_cycle_seconds = activity_slot_end_in_cycle
            if found_current_activity_for_this_court:
                break 
        if not found_current_activity_for_this_court:
            cumulative_duration_in_cycle_seconds = 0 
            for activity_assignment_future in court_activities_sequence:
                activity_future_duration_minutes = activity_assignment_future.duration_minutes if activity_assignment_future.duration_minutes is not None else 0
                activity_duration_seconds = activity_future_duration_minutes * 60
                activity_slot_start_in_cycle = cumulative_duration_in_cycle_seconds
                if activity_slot_start_in_cycle >= effective_time_within_activity_cycle:
                    next_activity_in_sequence_details = {
                        'name': activity_assignment_future.drill.name if activity_assignment_future.drill else activity_assignment_future.custom_activity_name,
                        'duration_minutes': activity_assignment_future.duration_minutes
                    }
                    break 
                cumulative_duration_in_cycle_seconds += activity_duration_seconds
        live_state['courts_data'].append({
            'court_number': court_num_loop,
            'current_activity': current_activity_details,
            'next_activity_in_block': next_activity_in_sequence_details,
            'assigned_players': [p.full_name for p in final_court_assignments_for_block.get(court_num_loop, [])]
        })


    print(f"--- Final live_state for session {session.id} (In Progress with Court Data): ---")
    pprint.pprint(live_state) 
    return live_state