# planning/payslip_services.py

from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from .models import Coach, CoachSessionCompletion, Payslip # Assuming Session is accessible via CoachSessionCompletion.session
from django.template.loader import render_to_string
from weasyprint import HTML
from django.core.files.base import ContentFile 
from django.contrib.auth import get_user_model # This import is correct

# You might need to import Session model directly if you access its fields extensively
# in other functions within this file, but for this function, indirect access is fine.

def get_payslip_data_for_coach(coach_id: int, year: int, month: int) -> dict | None:
    """
    Gathers all necessary data for a single coach's payslip for a specific period.
    """
    try:
        coach = Coach.objects.get(id=coach_id)
        if not coach.hourly_rate: 
            print(f"Coach {coach.id} ('{coach}') has no hourly rate set. Skipping payslip data generation.")
            return None
    except Coach.DoesNotExist:
        print(f"Coach with ID {coach_id} not found. Skipping payslip data generation.")
        return None

    if coach.user:
        coach_display_name = coach.user.get_full_name() or coach.user.username
        coach_identifier_for_filename = coach.user.username
    else:
        coach_display_name = coach.name 
        coach_identifier_for_filename = ''.join(e for e in coach.name if e.isalnum() or e == '_').lower()

    completions = CoachSessionCompletion.objects.filter(
        coach=coach,
        session__session_date__year=year,
        session__session_date__month=month,
        confirmed_for_payment=True 
    ).select_related(
        'session', 
        'session__school_group' 
    ).order_by('session__session_date', 'session__session_start_time')

    if not completions:
        return None

    session_details = []
    total_duration_minutes = Decimal('0')
    coach_hourly_rate = Decimal(str(coach.hourly_rate)) 

    for completion in completions:
        session_obj = completion.session
        duration_minutes = Decimal(str(session_obj.planned_duration_minutes))
        pay_for_session = (duration_minutes / Decimal('60.0')) * coach_hourly_rate
        total_duration_minutes += duration_minutes
        hours = int(duration_minutes // 60)
        minutes = int(duration_minutes % 60)
        duration_hours_str = f"{hours}h {minutes}m"
        session_details.append({
            'date': session_obj.session_date,
            'school_group_name': session_obj.school_group.name if session_obj.school_group else "N/A",
            'duration_minutes': session_obj.planned_duration_minutes, 
            'duration_hours_str': duration_hours_str, 
            'pay_for_session': pay_for_session.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        })

    total_hours_decimal = (total_duration_minutes / Decimal('60.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_pay = (total_hours_decimal * coach_hourly_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    total_duration_hours_int = int(total_duration_minutes // 60)
    total_duration_remainder_minutes_int = int(total_duration_minutes % 60)
    total_hours_str = f"{total_duration_hours_int}h {total_duration_remainder_minutes_int}m"
    
    try:
        month_name = timezone.datetime(year, month, 1).strftime('%B') # type: ignore
    except ValueError: 
        month_name = f"Month({month})"

    payslip_data = {
        'coach_name': coach_display_name,
        'coach_identifier_for_filename': coach_identifier_for_filename, 
        'hourly_rate': coach_hourly_rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'period_month_year_display': f"{month_name} {year}",
        'period_year': year,
        'period_month': month, 
        'sessions': session_details,
        'total_hours_decimal': total_hours_decimal, 
        'total_hours_str': total_hours_str, 
        'total_pay': total_pay,
        'generation_date': timezone.now().date(), 
    }
    return payslip_data

def create_all_payslips_for_period(year: int, month: int, generating_user_id: int | None, force_regeneration: bool = False) -> dict:
    """
    Generates and saves payslips for all eligible coaches for a given period.
    """
    User = get_user_model() # <<< --- ADD THIS LINE ---
    generating_user = None
    if generating_user_id:
        try:
            generating_user = User.objects.get(pk=generating_user_id)
        except User.DoesNotExist: # Now 'User' is defined
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
                    existing_payslip.delete() 
                    detailed_messages.append(f"  Successfully deleted existing payslip for {str(coach)}.")
                except Exception as e:
                    detailed_messages.append(f"  Error deleting existing payslip for {str(coach)}: {e}. Skipping regeneration.")
                    error_count +=1
                    continue 
            else:
                detailed_messages.append(f"  Payslip already exists for {str(coach)} for {month:02}/{year}. Skipping.")
                skipped_count += 1
                continue
        
        payslip_data = get_payslip_data_for_coach(coach.id, year, month) 

        if not payslip_data: 
            detailed_messages.append(f"  No payslip data (e.g., no confirmed sessions or no hourly rate) for {str(coach)} for {month:02}/{year}. Skipping.")
            skipped_count += 1
            continue
        
        pdf_bytes = generate_payslip_pdf_from_data(payslip_data)
        if not pdf_bytes:
            detailed_messages.append(f"  Failed to generate PDF for {str(coach)}. Skipping.")
            error_count += 1
            continue

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

            detailed_messages.append(f"  Successfully generated and saved payslip: {payslip_filename} for {str(coach)}")
            generated_count += 1
        except Exception as e:
            detailed_messages.append(f"  Error saving payslip record for {str(coach)}: {e}")
            error_count += 1
    
    summary_message = (
        f"Payslip Generation for {month:02}/{year}: "
        f"Successfully Generated: {generated_count}, Skipped: {skipped_count}, Errors: {error_count}."
    )
    detailed_messages.append(summary_message) 

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
    """
    User = get_user_model() # <<< --- ADD THIS LINE ---
    generating_user = None
    if generating_user_id:
        try:
            generating_user = User.objects.get(pk=generating_user_id)
        except User.DoesNotExist: # Now 'User' is defined
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
    
    pdf_bytes = generate_payslip_pdf_from_data(payslip_data) 
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
    """
    if not payslip_data:
        print("No payslip data provided to generate_payslip_pdf_from_data.")
        return None

    try:
        html_string = render_to_string('planning/payslip_template.html', {'payslip': payslip_data})
        pdf_bytes = HTML(string=html_string).write_pdf()
        return pdf_bytes
    except Exception as e:
        print(f"Error generating PDF for coach '{payslip_data.get('coach_name', 'Unknown')}': {e}")
        return None
