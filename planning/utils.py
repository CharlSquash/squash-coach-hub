# planning/utils.py

from datetime import date, timedelta, time as time_obj # Import time as time_obj to avoid conflict
from django.utils import timezone # For timezone awareness if needed, though dates are naive here
import calendar
import re 
# Import your models (ensure Session, SchoolGroup, Coach are imported if type hinting or direct use)
# from .models import Session, SchoolGroup, Coach # Example

def get_weekly_session_data(target_date_input: date):
    """
    Fetches and formats session data for the week containing the target_date_input.

    Args:
        target_date_input: A date object for any day within the desired week.

    Returns:
        A dictionary containing:
            'sessions_data': A list of dictionaries, each representing a session.
            'week_display_range': A string representing the week's date range (e.g., "May 05 - May 11, 2025").
            'week_start_date': The start date of the week (Monday).
            'week_end_date': The end date of the week (Sunday).
    """
    from .models import Session # Import locally to avoid circular import issues if utils is imported by models

    # Determine the start of the week (Monday)
    start_of_week = target_date_input - timedelta(days=target_date_input.weekday())
    # Determine the end of the week (Sunday)
    end_of_week = start_of_week + timedelta(days=6)

    # Fetch sessions for the entire week, ordered by date and start time
    sessions_in_week = Session.objects.filter(
        session_date__gte=start_of_week,
        session_date__lte=end_of_week
    ).select_related(
        'school_group'  # For accessing school_group.name
    ).prefetch_related(
        'coaches_attending' # For accessing coach names
    ).order_by('session_date', 'session_start_time')

    formatted_sessions = []
    for session in sessions_in_week:
        session_start_time = session.session_start_time if session.session_start_time else time_obj.min
        
        # Calculate end time for the time slot display
        # Naive datetime for calculation, assuming session_date and session_start_time are naive
        from datetime import datetime # Local import for datetime class
        naive_start_dt = datetime.combine(session.session_date, session_start_time)
        naive_end_dt = naive_start_dt + timedelta(minutes=session.planned_duration_minutes)
        
        time_slot = f"{session_start_time.strftime('%H:%M')} - {naive_end_dt.strftime('%H:%M')}"

        coaches_list = [coach.name for coach in session.coaches_attending.all()]
        coaches_str = ", ".join(coaches_list) if coaches_list else "N/A"

        formatted_sessions.append({
            'date': session.session_date.strftime('%Y-%m-%d'),
            'day': session.session_date.strftime('%A'), # Full day name (e.g., "Monday")
            'time_slot': time_slot,
            'class_name': session.school_group.name if session.school_group else "N/A",
            'coaches': coaches_str,
            'venue': session.venue_name if session.venue_name else "N/A",
            'status': "Cancelled" if session.is_cancelled else "Scheduled",
        })

    week_display_range = f"{start_of_week.strftime('%B %d')} - {end_of_week.strftime('%B %d, %Y')}"

    return {
        'sessions_data': formatted_sessions,
        'week_display_range': week_display_range,
        'week_start_date': start_of_week,
        'week_end_date': end_of_week,
    }


def get_month_start_end(year: int, month: int) -> tuple[date, date]:
    """
    Calculates the first and last day of a given month and year.
    """
    # Get the number of days in the given month and year
    _, num_days = calendar.monthrange(year, month)
    
    # First day of the month
    start_date = date(year, month, 1)
    
    # Last day of the month
    end_date = date(year, month, num_days)
    
    return start_date, end_date

def get_month_choices() -> list[tuple[int, str]]:
    """
    Returns a list of tuples for month choices (e.g., for a form select field).
    """
    return [(i, calendar.month_name[i]) for i in range(1, 13)]

def get_year_choices() -> list[int]:
    """
    Returns a list of years (e.g., for a form select field).
    Adjust the range as needed.
    """
    current_year = timezone.now().year
    return list(range(current_year - 5, current_year + 2)) # Example: 5 years back, 1 year forward
# Example usage (for testing this function directly if needed):
# if __name__ == '__main__':
#   # This part would only run if you execute this utils.py file directly
#   # and would require Django setup.
#   # For actual use, call this function from your views.py.
#   today = date.today()
#   weekly_data = get_weekly_session_data(today)
#   print(f"Schedule for week: {weekly_data['week_display_range']}")
#   for session_data in weekly_data['sessions_data']:
#       print(session_data)

def parse_grade_from_string(grade_str: str) -> int | None:
    """
    Parses a grade string like 'Gr 8' or '8' and returns the corresponding integer.
    Returns None if no valid grade number is found.
    """
    if not grade_str or not isinstance(grade_str, str):
        return None
    
    # Find any numbers in the string
    numbers = re.findall(r'\d+', grade_str)
    if numbers:
        return int(numbers[0])
    return None