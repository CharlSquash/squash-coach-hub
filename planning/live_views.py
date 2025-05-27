# planning/live_views.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, Http404
from django.utils import timezone
from datetime import datetime as dt_class # For parsing sim_time_iso
from django.db.models import Max # Import Max for aggregation

from .models import Session, TimeBlock # Import Session and any other models needed directly by these views
from .live_session_utils import get_session_live_state # Import your core logic function

# Define your user test function (e.g., is_coach) or import it
def is_coach(user):
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(is_coach, login_url='login')
def live_session_page_view(request, session_id):
    """
    Renders the main page for the live session display.
    This page will contain JavaScript to fetch and display live data.
    """
    session = get_object_or_404(
        Session.objects.select_related('school_group'), 
        pk=session_id
    )

    # --- MODIFIED LOGIC FOR number_of_courts ---
    # Determine the maximum number of courts used in any time block for this session
    all_time_blocks = TimeBlock.objects.filter(session=session)
    number_of_courts = 1 # Default to 1

    if all_time_blocks.exists():
        max_courts_data = all_time_blocks.aggregate(max_courts=Max('number_of_courts'))
        if max_courts_data['max_courts'] is not None:
            number_of_courts = max_courts_data['max_courts']
    # --- END OF MODIFIED LOGIC ---

    context = {
        'session': session,
        'number_of_courts': number_of_courts, # Now reflects the max for the session
        'page_title': f"Live: {session.school_group.name if session.school_group else 'Session'} ({session.session_date.strftime('%d %b')})",
    }
    return render(request, 'planning/live_session_display.html', context)


@login_required
@user_passes_test(is_coach, login_url='login') 
def live_session_update_api(request, session_id):
    """
    API endpoint that returns the current live state of a session.
    Accepts an optional 'sim_time_iso' GET parameter for time simulation.
    """
    print(f"--- live_session_update_api CALLED for session_id: {session_id} ---") 
    print(f"--- GET params: {request.GET} ---") 

    sim_time_iso = request.GET.get('sim_time_iso')
    effective_current_time = timezone.now() 

    if sim_time_iso:
        try:
            try:
                parsed_time = dt_class.fromisoformat(sim_time_iso)
            except ValueError: 
                if not sim_time_iso.endswith('Z') and '+' not in sim_time_iso and '-' not in sim_time_iso[10:]:
                    parsed_time = dt_class.fromisoformat(sim_time_iso + 'Z') 
                else:
                    raise

            if timezone.is_naive(parsed_time):
                effective_current_time = timezone.make_aware(parsed_time, timezone.get_current_timezone())
            else:
                effective_current_time = timezone.localtime(parsed_time)
            
            print(f"--- Using simulated time: {effective_current_time.isoformat()} (Effective TZ: {effective_current_time.tzinfo}) ---")
        except ValueError as e:
            print(f"--- Invalid sim_time_iso format: '{sim_time_iso}'. Error: {e}. Using real time. ---")
            effective_current_time = timezone.now() # Fallback to real time
    else:
        print(f"--- Using real time (no sim_time_iso provided). Current server time: {effective_current_time.isoformat()} ---")

    try:
        session_obj = get_object_or_404(Session, pk=session_id)
        # It's good practice to prefetch related data for session_obj here if get_session_live_state
        # relies on it and session_obj isn't already optimized.
        # For example:
        # session_obj = get_object_or_404(
        # Session.objects.select_related('school_group')
        # .prefetch_related(
        # Prefetch('time_blocks', queryset=TimeBlock.objects.order_by('start_offset_minutes')
        # .prefetch_related(
        # Prefetch('activities', queryset=ActivityAssignment.objects.select_related('drill').order_by('court_number', 'order'))
        # )
        # ),
        # 'attendees'
        # ),
        # pk=session_id
        # )
        live_state = get_session_live_state(session_obj, effective_current_time)
    except Http404:
        print(f"--- live_session_update_api: Session {session_id} not found ---")
        return JsonResponse({'error': 'Session not found.'}, status=404)
    except Exception as e:
        print(f"--- live_session_update_api: Error calling get_session_live_state for session {session_id}: {e} ---")
        import traceback
        traceback.print_exc() 
        return JsonResponse({'error': 'Error calculating session state.'}, status=500)

    if live_state is None: # Should ideally not happen if get_session_live_state always returns a dict
        print(f"--- live_session_update_api: get_session_live_state returned None for session {session_id} ---")
        return JsonResponse({'error': 'Failed to calculate session state (helper returned None).'}, status=500)
    
    return JsonResponse(live_state)