# planning/payslip_services.py

from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from .models import Coach, CoachSessionCompletion, Payslip # Assuming Session is accessible via CoachSessionCompletion.session
from django.template.loader import render_to_string
from weasyprint import HTML
from django.core.files.base import ContentFile 
from django.contrib.auth import get_user_model
# You might need to import Session model directly if you access its fields extensively
# in other functions within this file, but for this function, indirect access is fine.

def get_payslip_data_for_coach(coach_id: int, year: int, month: int) -> dict | None:
    """
    Gathers all necessary data for a single coach's payslip for a specific period.

    Args:
        coach_id: The ID of the Coach.
        year: The year of the payslip period.
        month: The month (1-12) of the payslip period.

    Returns:
        A dictionary containing all payslip data, or None if the coach is not found,
        has no hourly rate, or has no confirmed sessions for the period.
    """
    try:
        coach = Coach.objects.get(id=coach_id)
        if not coach.hourly_rate: # Check if hourly_rate is set and not zero
            # You might want to log this case or handle it differently
            print(f"Coach {coach.id} ('{coach}') has no hourly rate set. Skipping payslip data generation.")
            return None
    except Coach.DoesNotExist:
        print(f"Coach with ID {coach_id} not found. Skipping payslip data generation.")
        return None

    # Determine the coach's display name (using logic from Coach model's __str__)
    if coach.user:
        coach_display_name = coach.user.get_full_name() or coach.user.username
        coach_identifier_for_filename = coach.user.username
    else:
        coach_display_name = coach.name # Fallback to the Coach's name field
        # Create a basic filename-safe identifier from the name
        coach_identifier_for_filename = ''.join(e for e in coach.name if e.isalnum() or e == '_').lower()


    # Find completed and confirmed sessions for the coach in the given month and year
    # Using 'session__session_date' as confirmed from your CoachSessionCompletion model
    completions = CoachSessionCompletion.objects.filter(
        coach=coach,
        session__session_date__year=year,
        session__session_date__month=month,
        confirmed_for_payment=True  # Crucial filter
    ).select_related(
        'session', # To access session fields like planned_duration_minutes, session_date
        'session__school_group'  # Assuming SchoolGroup is linked from Session and has a 'name' attribute
    ).order_by('session__session_date', 'session__session_start_time') # Consistent ordering

    if not completions:
        # No confirmed sessions for this period for this coach
        # print(f"No confirmed sessions found for coach {coach_display_name} for {month}/{year}.")
        return None

    session_details = []
    total_duration_minutes = Decimal('0')
    coach_hourly_rate = Decimal(str(coach.hourly_rate)) # Ensure hourly_rate is Decimal for precision

    for completion in completions:
        session_obj = completion.session
        # *** UPDATED to use planned_duration_minutes from your Session model ***
        duration_minutes = Decimal(str(session_obj.planned_duration_minutes))
        
        pay_for_session = (duration_minutes / Decimal('60.0')) * coach_hourly_rate
        total_duration_minutes += duration_minutes
        
        # Format duration as "Xh Ym"
        hours = int(duration_minutes // 60)
        minutes = int(duration_minutes % 60)
        duration_hours_str = f"{hours}h {minutes}m"

        session_details.append({
            'date': session_obj.session_date,
            'school_group_name': session_obj.school_group.name if session_obj.school_group else "N/A",
            'duration_minutes': session_obj.planned_duration_minutes, # Original duration in minutes
            'duration_hours_str': duration_hours_str, # Formatted duration string
            'pay_for_session': pay_for_session.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        })

    total_hours_decimal = (total_duration_minutes / Decimal('60.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_pay = (total_hours_decimal * coach_hourly_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Format total duration as "Xh Ym"
    total_duration_hours_int = int(total_duration_minutes // 60)
    total_duration_remainder_minutes_int = int(total_duration_minutes % 60)
    total_hours_str = f"{total_duration_hours_int}h {total_duration_remainder_minutes_int}m"
    
    # Get the name of the month
    try:
        # Using a fixed day (like 1) to create a datetime object for strftime
        month_name = timezone.datetime(year, month, 1).strftime('%B')
    except ValueError: 
        # This might happen if year/month are somehow outside valid ranges, though type hints should help.
        month_name = f"Month({month})"


    payslip_data = {
        'coach_name': coach_display_name,
        'coach_identifier_for_filename': coach_identifier_for_filename, # For use in PDF filenames
        'hourly_rate': coach_hourly_rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'period_month_year_display': f"{month_name} {year}",
        'period_year': year,
        'period_month': month, # Numerical month
        'sessions': session_details,
        'total_hours_decimal': total_hours_decimal, # Total hours as a decimal (e.g., 7.50)
        'total_hours_str': total_hours_str, # Formatted total hours string (e.g., "7h 30m")
        'total_pay': total_pay,
        'generation_date': timezone.now().date(), # Date when the payslip data dictionary is generated
    }
    return payslip_data

def create_all_payslips_for_period(year: int, month: int, generating_user_id: int | None, force_regeneration: bool = False) -> dict:
    """
    Generates and saves payslips for all eligible coaches for a given period.

    Args:
        year: The year for payslip generation.
        month: The month (1-12) for payslip generation.
        generating_user_id: The ID of the user (superuser) initiating the generation.
                              Can be None if generated by a system process without a specific user.
        force_regeneration: If True, existing payslips for the period will be deleted and regenerated.

    Returns:
        A dictionary containing counts of generated, skipped, and errored payslips,
        a summary message, and a list of detailed log messages.
    """
    
    generating_user = None
    if generating_user_id:
        try:
            generating_user = User.objects.get(pk=generating_user_id)
        except User.DoesNotExist:
            # Handle case where user_id is provided but user doesn't exist
            # This might be an error condition or you might default to None
            # For now, let's log and proceed as if no user was specified for 'generated_by'
            print(f"Warning: User with ID {generating_user_id} not found for marking 'generated_by'.")

    eligible_coaches = Coach.objects.filter(is_active=True, hourly_rate__isnull=False).exclude(hourly_rate=0)
    
    if not eligible_coaches.exists():
        return {
            'generated_count': 0, 'skipped_count': 0, 'error_count': 0,
            'summary_message': "No active coaches with an hourly rate found. No payslips to generate.",
            'details': ["No active coaches with an hourly rate found."]
        }

    generated_count = 0
    skipped_count = 0
    error_count = 0
    detailed_messages = []

    detailed_messages.append(f"Starting payslip generation for {month:02}/{year}.")
    if generating_user:
        detailed_messages.append(f"Payslips will be marked as generated by: {generating_user.username}")


    for coach in eligible_coaches:
        detailed_messages.append(f"Processing coach: {str(coach)} (ID: {coach.id})...")

        existing_payslip = Payslip.objects.filter(coach=coach, year=year, month=month).first()
        if existing_payslip:
            if force_regeneration:
                detailed_messages.append(f"  Existing payslip found for {str(coach)} for {month:02}/{year}. Forcing regeneration...")
                try:
                    existing_payslip.delete() # Delete the old one
                    detailed_messages.append(f"  Successfully deleted existing payslip for {str(coach)}.")
                except Exception as e:
                    detailed_messages.append(f"  Error deleting existing payslip for {str(coach)}: {e}. Skipping regeneration.")
                    error_count +=1
                    continue # Skip to next coach if deletion fails
            else:
                detailed_messages.append(f"  Payslip already exists for {str(coach)} for {month:02}/{year}. Skipping.")
                skipped_count += 1
                continue
        
        # Use the existing functions from your payslip_services.py
        payslip_data = get_payslip_data_for_coach(coach.id, year, month) 

        if not payslip_data: # get_payslip_data_for_coach returns None if no data or coach issue
            detailed_messages.append(f"  No payslip data (e.g., no confirmed sessions or no hourly rate) for {str(coach)} for {month:02}/{year}. Skipping.")
            skipped_count += 1
            continue
        
        pdf_bytes = generate_payslip_pdf_from_data(payslip_data)
        if not pdf_bytes:
            detailed_messages.append(f"  Failed to generate PDF for {str(coach)}. Skipping.")
            error_count += 1
            continue

        # Ensure 'coach_identifier_for_filename' is in payslip_data, fallback if not
        coach_id_filename = payslip_data.get('coach_identifier_for_filename', f"coach_{coach.id}_unknown")
        payslip_filename = f"payslip_{coach_id_filename}_{year}_{month:02d}.pdf"
        
        try:
            new_payslip = Payslip(
                coach=coach,
                year=year,
                month=month,
                total_amount=payslip_data.get('total_pay', Decimal('0.00')), # Ensure 'total_pay' exists, default to 0
                generated_by=generating_user # This can be None if generating_user_id was None or user not found
            )
            # Save the file content
            new_payslip.file.save(payslip_filename, ContentFile(pdf_bytes), save=False) # save=False initially
            new_payslip.save() # Now save the model instance with the file

            detailed_messages.append(f"  Successfully generated and saved payslip: {payslip_filename} for {str(coach)}")
            generated_count += 1
        except Exception as e:
            detailed_messages.append(f"  Error saving payslip record for {str(coach)}: {e}")
            error_count += 1
    
    summary_message = (
        f"Payslip Generation for {month:02}/{year}: "
        f"Successfully Generated: {generated_count}, Skipped: {skipped_count}, Errors: {error_count}."
    )
    detailed_messages.append(summary_message) # Add final summary to details as well

    return {
        'generated_count': generated_count,
        'skipped_count': skipped_count,
        'error_count': error_count,
        'summary_message': summary_message,
        'details': detailed_messages
    }

def generate_payslip_for_single_coach(coach_id: int, year: int, month: int, generating_user_id: int | None, force_regeneration: bool = False) -> dict:
    """
    Generates and saves a payslip for a single coach for a given period.

    Args:
        coach_id: The ID of the Coach.
        year: The year for payslip generation.
        month: The month (1-12) for payslip generation.
        generating_user_id: The ID of the user (superuser) initiating the generation.
        force_regeneration: If True, an existing payslip for the period will be deleted and regenerated.

    Returns:
        A dictionary containing status, message, and details.
        Example: {'status': 'success', 'message': 'Payslip generated for Coach X.', 'details': ['Log message...']}
    """
    User = get_user_model() # Get User model
    generating_user = None
    if generating_user_id:
        try:
            generating_user = User.objects.get(pk=generating_user_id)
        except User.DoesNotExist:
            # Log this, but proceed as if no user was specified for 'generated_by'
            print(f"Warning: User with ID {generating_user_id} not found for marking 'generated_by'.")

    detailed_messages = []
    
    try:
        coach = Coach.objects.get(id=coach_id)
    except Coach.DoesNotExist:
        return {'status': 'error', 'message': f"Coach with ID {coach_id} not found.", 'details': [f"Coach with ID {coach_id} not found."]}

    detailed_messages.append(f"Processing payslip for coach: {str(coach)} (ID: {coach.id}) for {month:02}/{year}.")

    existing_payslip = Payslip.objects.filter(coach=coach, year=year, month=month).first()
    if existing_payslip:
        if force_regeneration:
            detailed_messages.append(f"  Existing payslip found. Forcing regeneration...")
            try:
                existing_payslip.delete()
                detailed_messages.append(f"  Successfully deleted existing payslip.")
            except Exception as e:
                detailed_messages.append(f"  Error deleting existing payslip: {e}. Aborting.")
                return {'status': 'error', 'message': f"Error deleting existing payslip for {str(coach)}.", 'details': detailed_messages}
        else:
            detailed_messages.append(f"  Payslip already exists. Skipping generation (force_regeneration is False).")
            return {'status': 'skipped', 'message': f"Payslip already exists for {str(coach)} for {month:02}/{year}. Skipped.", 'details': detailed_messages}
            
    payslip_data = get_payslip_data_for_coach(coach.id, year, month) 

    if not payslip_data:
        detailed_messages.append(f"  No payslip data (e.g., no confirmed sessions or no hourly rate). Skipping.")
        return {'status': 'skipped', 'message': f"No payslip data for {str(coach)} for {month:02}/{year}. Skipped.", 'details': detailed_messages}
    
    pdf_bytes = generate_payslip_pdf_from_data(payslip_data) # Assumes this function exists and works
    if not pdf_bytes:
        detailed_messages.append(f"  Failed to generate PDF. Skipping.")
        return {'status': 'error', 'message': f"Failed to generate PDF for {str(coach)}.", 'details': detailed_messages}

    coach_id_filename = payslip_data.get('coach_identifier_for_filename', f"coach_{coach.id}_unknown")
    payslip_filename = f"payslip_{coach_id_filename}_{year}_{month:02d}.pdf"
    
    try:
        new_payslip = Payslip(
            coach=coach,
            year=year,
            month=month,
            total_amount=payslip_data.get('total_pay', Decimal('0.00')),
            generated_by=generating_user
        )
        new_payslip.file.save(payslip_filename, ContentFile(pdf_bytes), save=False)
        new_payslip.save()

        detailed_messages.append(f"  Successfully generated and saved payslip: {payslip_filename}")
        return {
            'status': 'success', 
            'message': f"Successfully generated payslip {payslip_filename} for {str(coach)}.",
            'details': detailed_messages
        }
    except Exception as e:
        detailed_messages.append(f"  Error saving payslip record: {e}")
        return {
            'status': 'error', 
            'message': f"Error saving payslip record for {str(coach)}: {e}",
            'details': detailed_messages
        }

def generate_payslip_pdf_from_data(payslip_data: dict | None) -> bytes | None:
    """
    Generates a PDF payslip from the provided payslip_data dictionary.

    Args:
        payslip_data: A dictionary containing all necessary data for the payslip,
                      typically generated by get_payslip_data_for_coach.

    Returns:
        A byte string containing the PDF data, or None if input data is None
        or an error occurs during PDF generation.
    """
    if not payslip_data:
        print("No payslip data provided to generate_payslip_pdf_from_data.")
        return None

    try:
        # Render the HTML template with the payslip data
        # The context key 'payslip' matches what's used in payslip_template.html
        html_string = render_to_string('planning/payslip_template.html', {'payslip': payslip_data})
        
        # Convert the rendered HTML to PDF bytes
        # You can pass a base_url argument to HTML() if your template refers to external
        # static files (CSS, images) that WeasyPrint needs to resolve.
        # For embedded styles, this is usually not needed.
        # e.g., HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        # However, for this simple template with embedded CSS, it should work directly.
        pdf_bytes = HTML(string=html_string).write_pdf()
        
        return pdf_bytes
    except Exception as e:
        # Log the error for debugging
        # Consider using Django's logging framework for more robust error handling
        print(f"Error generating PDF for coach '{payslip_data.get('coach_name', 'Unknown')}': {e}")
        # Depending on your error handling strategy, you might want to raise the exception
        # or return None to indicate failure.
        return None    