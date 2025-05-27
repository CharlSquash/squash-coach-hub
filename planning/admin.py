# planning/admin.py
from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from datetime import date, timedelta # For default dates in the form

from django.contrib.auth import get_user_model

from .models import (
    SchoolGroup, Player, Coach, Drill, Session, TimeBlock,
    ActivityAssignment, SessionAssessment, CourtSprintRecord, 
    VolleyRecord, BackwallDriveRecord, MatchResult,
    ManualCourtAssignment, CoachAvailability, Payslip,
    ScheduledClass,
    CoachSessionCompletion,
    Venue
)

# Import the service function for generating sessions
from .session_generation_service import generate_sessions_for_rules # Adjust path if it's in utils.py

User = get_user_model()


# --- Form for Payslip Generation (remains the same) ---
class PeriodCoachSelectionForm(forms.Form):
    year = forms.IntegerField(label="Year", initial=timezone.now().year, help_text="Enter the year for payslip generation (e.g., 2025).")
    month = forms.IntegerField(label="Month", min_value=1, max_value=12, initial=timezone.now().month, help_text="Enter the month for payslip generation (1-12).")
    specific_coach = forms.ModelChoiceField(
        queryset=Coach.objects.filter(is_active=True), required=False, 
        label="Specific Coach (Optional)", help_text="Leave blank to generate for ALL eligible active coaches. Select a coach to generate only for them."
    )
    force_regeneration = forms.BooleanField(label="Force Regeneration", required=False, initial=False, help_text="If checked, any existing payslip for the selected coach(es) and period will be deleted and regenerated.")

# --- NEW Form for Session Generation Date Range ---
class GenerateSessionsForm(forms.Form):
    default_start_date = timezone.now().date()
    default_end_date = default_start_date + timedelta(weeks=4) # Default to 4 weeks from today

    start_date = forms.DateField(
        label="Start Date",
        initial=default_start_date,
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="Generate sessions starting from this date."
    )
    end_date = forms.DateField(
        label="End Date",
        initial=default_end_date,
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="Generate sessions up to and including this date."
    )
    overwrite_clashing_manual_sessions = forms.BooleanField(
        label="Overwrite clashing manual sessions?",
        required=False,
        initial=False,
        help_text="If checked, any manually created session that clashes (same group, date, time) will be updated and linked to the generating rule. Otherwise, clashes are skipped."
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError("End date cannot be before start date.")
        return cleaned_data


# --- Admin Registrations ---
@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'notes', 'is_active')
    list_filter = ('is_active',); search_fields = ('name', 'address', 'notes')
    fields = ('name', 'address', 'notes', 'is_active')

@admin.register(SchoolGroup)
class SchoolGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'description'); search_fields = ('name',)

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('full_name','contact_number', 'parent_contact_number', 'skill_level', 'is_active')
    list_filter = ('skill_level', 'is_active', 'school_groups'); search_fields = ('first_name', 'last_name')
    filter_horizontal = ('school_groups',)

@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin): # CoachAdmin (remains the same)
    list_display = ('name', 'user_link', 'email', 'phone', 'is_active', 'hourly_rate')
    search_fields = ('name', 'email', 'user__username', 'user__first_name', 'user__last_name')
    list_filter = ('is_active', 'user'); fields = ('user', 'name', 'phone', 'email', 'is_active', 'hourly_rate')
    raw_id_fields = ('user',); actions = ['trigger_payslip_generation_action']
    @admin.display(description='Linked User Account')
    def user_link(self, obj):
        if obj.user: url = reverse('admin:auth_user_change', args=[obj.user.pk]); return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return "-"
    user_link.admin_order_field = 'user__username'
    def trigger_payslip_generation_action(self, request, queryset): # Payslip action logic (remains the same)
        from .payslip_services import generate_payslip_for_single_coach # Local import
        if request.method == 'POST' and 'process_payslips' in request.POST:
            form = PeriodCoachSelectionForm(request.POST) 
            if form.is_valid():
                year = form.cleaned_data['year']; month = form.cleaned_data['month']; force = form.cleaned_data['force_regeneration']
                selected_coach_instance = form.cleaned_data.get('specific_coach'); generating_user_id = request.user.id if request.user.is_authenticated else None
                if selected_coach_instance:
                    result = generate_payslip_for_single_coach(coach_id=selected_coach_instance.id, year=year, month=month, generating_user_id=generating_user_id, force_regeneration=force)
                    if result.get('status') == 'success': self.message_user(request, result.get('message', 'Payslip generated successfully.'), messages.SUCCESS)
                    elif result.get('status') == 'skipped': self.message_user(request, result.get('message', 'Payslip skipped.'), messages.WARNING)
                    else: self.message_user(request, result.get('message', 'An error occurred.'), messages.ERROR)
                    if result.get('details'): [self.message_user(request, msg, messages.INFO) for msg in result['details']]
                else: 
                    result = create_all_payslips_for_period(year=year, month=month, generating_user_id=generating_user_id, force_regeneration=force)
                    if result.get('summary_message'):
                        if result.get('error_count', 0) > 0 or (result.get('generated_count', 0) == 0 and result.get('skipped_count',0) > 0): self.message_user(request, result['summary_message'], messages.WARNING)
                        elif result.get('generated_count', 0) > 0: self.message_user(request, result['summary_message'], messages.SUCCESS)
                        else: self.message_user(request, result['summary_message'], messages.INFO)
                    if result.get('details'): [self.message_user(request, msg, messages.INFO) for msg in result['details'] if msg != result.get('summary_message') and not msg.startswith("Starting payslip generation")]
                return HttpResponseRedirect(request.get_full_path()) 
            else: self.message_user(request, "Form is invalid. Please correct the errors displayed on the form.", messages.ERROR)
        else: form = PeriodCoachSelectionForm() 
        context = {**self.admin_site.each_context(request), 'title': 'Generate Payslip(s) for Period', 'form': form, 'opts': self.model._meta, 'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME, 'queryset': queryset, }
        return render(request, 'admin/payslip_generation_form_template.html', context)
    trigger_payslip_generation_action.short_description = "Generate Payslip(s) for Period"

@admin.register(Drill)
class DrillAdmin(admin.ModelAdmin): # DrillAdmin (remains the same)
    list_display = ('name', 'duration_minutes_default', 'ideal_num_players', 'suitable_for_any')
    list_filter = ('suitable_for_any',); search_fields = ('name', 'description')
    fieldsets = ((None, {'fields': ('name', 'description', 'duration_minutes_default')}), ('Player Suitability', {'fields': ('ideal_num_players', 'suitable_for_any')}),)

class TimeBlockInline(admin.TabularInline): # TimeBlockInline (remains the same)
    model = TimeBlock; extra = 1
    fields = ('start_offset_minutes', 'duration_minutes', 'number_of_courts', 'rotation_interval_minutes', 'block_focus')
    ordering = ('start_offset_minutes',)

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin): # SessionAdmin (remains largely the same, with venue FK)
    list_display = ('__str__', 'session_date', 'session_start_time', 'school_group', 'venue', 'planned_duration_minutes', 'get_assigned_coaches_display', 'is_cancelled', 'assessments_complete', 'generated_from_rule_display')
    list_filter = ('session_date', 'is_cancelled', 'venue', 'school_group', 'coaches_attending', 'assessments_complete', 'generated_from_rule')
    search_fields = ('notes', 'school_group__name', 'venue__name', 'coaches_attending__name')
    date_hierarchy = 'session_date'; filter_horizontal = ('coaches_attending', 'attendees',) 
    inlines = [TimeBlockInline] ; readonly_fields = ('assessments_complete',) 
    fields = ('school_group', 'session_date', 'session_start_time', 'planned_duration_minutes', 'venue', 'is_cancelled', 'coaches_attending', 'attendees', 'notes', 'assessments_complete', 'generated_from_rule')
    autocomplete_fields = ['venue', 'school_group', 'generated_from_rule'] # Added generated_from_rule
    def save_model(self, request, obj, form, change): # save_model (remains the same)
        super().save_model(request, obj, form, change)
        if obj.school_group and (not change or (change and not Session.objects.get(pk=obj.pk).school_group)):
            players_in_group = obj.school_group.players.filter(is_active=True); obj.attendees.set(players_in_group)
    @admin.display(description='Assigned Coaches')
    def get_assigned_coaches_display(self, obj): return ", ".join([coach.name for coach in obj.coaches_attending.all()])
    @admin.display(description='Generated by Rule', ordering='generated_from_rule__school_group__name')
    def generated_from_rule_display(self, obj): return str(obj.generated_from_rule) if obj.generated_from_rule else "-"

@admin.register(SessionAssessment)
class SessionAssessmentAdmin(admin.ModelAdmin): # SessionAssessmentAdmin (remains the same)
    list_display = ('player', 'session_date_display', 'submitted_by_user', 'effort_rating', 'focus_rating', 'is_hidden', 'superuser_reviewed', 'date_recorded')
    list_filter = ('session__session_date', 'player', 'submitted_by', 'is_hidden', 'superuser_reviewed', 'effort_rating', 'focus_rating')
    search_fields = ('player__first_name', 'player__last_name', 'session__school_group__name', 'submitted_by__username', 'submitted_by__first_name', 'submitted_by__last_name', 'coach_notes')
    readonly_fields = ('date_recorded',); fieldsets = ((None, {'fields': ('player', 'session', 'submitted_by')}),('Ratings', {'fields': ('effort_rating', 'focus_rating', 'resilience_rating', 'composure_rating', 'decision_making_rating')}),('Notes & Visibility', {'fields': ('coach_notes', 'is_hidden', 'superuser_reviewed')}),('Metadata', {'fields': ('date_recorded',), 'classes': ('collapse',)}),)
    def session_date_display(self, obj):
        if obj.session: return obj.session.session_date
        return None
    session_date_display.short_description = 'Session Date'; session_date_display.admin_order_field = 'session__session_date'
    def submitted_by_user(self, obj):
        if obj.submitted_by: return obj.submitted_by.get_full_name() or obj.submitted_by.username
        return None
    submitted_by_user.short_description = 'Assessed By'; submitted_by_user.admin_order_field = 'submitted_by'
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None: 
            if request.user.is_staff:
                if 'submitted_by' in form.base_fields: form.base_fields['submitted_by'].initial = request.user; form.base_fields['submitted_by'].widget.attrs['disabled'] = True 
        else: 
            if 'submitted_by' in form.base_fields: form.base_fields['submitted_by'].widget.attrs['disabled'] = True
        if not request.user.is_superuser:
            if 'is_hidden' in form.base_fields: form.base_fields['is_hidden'].disabled = True
            if 'superuser_reviewed' in form.base_fields: form.base_fields['superuser_reviewed'].disabled = True
        return form
    def save_model(self, request, obj, form, change):
        if not obj.pk: obj.submitted_by = request.user
        super().save_model(request, obj, form, change)
    def has_change_permission(self, request, obj=None):
        if not obj: return super().has_change_permission(request, obj)
        if request.user.is_superuser: return True
        if obj.submitted_by == request.user: return True
        return False 
    def has_delete_permission(self, request, obj=None):
        if not obj: return super().has_delete_permission(request, obj)
        if request.user.is_superuser: return True
        if obj.submitted_by == request.user: return True
        return False 
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs 
        return qs.filter(is_hidden=False)

# --- UPDATED ScheduledClassAdmin with Action ---
@admin.register(ScheduledClass)
class ScheduledClassAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'school_group', 'day_of_week', 'start_time', 'default_duration_minutes', 'default_venue', 'is_active', 'display_default_coaches')
    list_filter = ('school_group', 'day_of_week', 'is_active', 'default_venue', 'default_coaches')
    search_fields = ('school_group__name', 'default_venue__name', 'notes_for_rule')
    filter_horizontal = ('default_coaches',)
    fieldsets = (
        (None, {'fields': ('school_group', 'day_of_week', 'start_time', 'is_active')}),
        ('Default Session Details', {'fields': ('default_duration_minutes', 'default_venue', 'default_coaches')}),
        ('Notes', {'fields': ('notes_for_rule',), 'classes': ('collapse',)}),
    )
    autocomplete_fields = ['school_group', 'default_venue']
    actions = ['generate_sessions_action'] # <-- Added action

    def display_default_coaches(self, obj):
        return ", ".join([coach.name for coach in obj.default_coaches.all()])
    display_default_coaches.short_description = 'Default Coaches'

    def generate_sessions_action(self, request, queryset):
        """
        Admin action to generate sessions for the selected ScheduledClass rules.
        """
        form = GenerateSessionsForm(request.POST or None) # Use our new form

        if 'generate_sessions_submit' in request.POST: # Check for our form's submit button
            if form.is_valid():
                start_date = form.cleaned_data['start_date']
                end_date = form.cleaned_data['end_date']
                overwrite = form.cleaned_data['overwrite_clashing_manual_sessions']
                
                # Call the service function
                results = generate_sessions_for_rules(queryset, start_date, end_date, overwrite)

                # Display messages
                self.message_user(request, f"Session Generation Complete: {results['created']} created, {results['skipped_exists']} skipped (already exist/clashed), {results['errors']} errors.", messages.SUCCESS if results['errors'] == 0 else messages.WARNING)
                for detail in results['details']:
                    self.message_user(request, detail, messages.INFO)
                
                return HttpResponseRedirect(request.get_full_path()) # Redirect to avoid re-POST on refresh
            else:
                # Form is not valid, errors will be displayed by the template
                self.message_user(request, "Please correct the errors below.", messages.ERROR)
        
        # If not POSTing the generation form, or if form was invalid, display the intermediate page
        context = {
            **self.admin_site.each_context(request),
            'title': 'Generate Sessions from Rules',
            'queryset': queryset, # The selected ScheduledClass rules
            'form': form, # The date range form
            'opts': self.model._meta,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME, # Needed by admin template
        }
        # You'll need to create this template: admin/planning/scheduledclass/generate_sessions_form.html
        return render(request, 'admin/planning/scheduledclass/generate_sessions_intermediate.html', context)
    generate_sessions_action.short_description = "Generate Sessions for selected rules"
# --- END UPDATED ScheduledClassAdmin ---

# Other admin registrations remain the same
admin.site.register(CourtSprintRecord); admin.site.register(VolleyRecord)
admin.site.register(BackwallDriveRecord); admin.site.register(MatchResult)
admin.site.register(ManualCourtAssignment)

@admin.register(CoachAvailability)
class CoachAvailabilityAdmin(admin.ModelAdmin): # CoachAvailabilityAdmin (remains the same)
    list_display = ('coach_username', 'session_display', 'is_available', 'timestamp', 'last_action', 'status_updated_at') 
    list_filter = ('is_available', 'session__session_date', 'coach__username', 'last_action') 
    search_fields = ('coach__username', 'session__school_group__name', 'notes')
    list_select_related = ('coach', 'session', 'session__school_group') 
    readonly_fields = ('timestamp', 'status_updated_at', 'last_action') 
    fields = ('coach', 'session', 'is_available', 'notes', 'timestamp', 'last_action', 'status_updated_at') 
    raw_id_fields = ('coach', 'session',)
    def coach_username(self, obj): return obj.coach.username if obj.coach else None 
    coach_username.admin_order_field = 'coach__username'
    def session_display(self, obj): return str(obj.session)
    session_display.admin_order_field = 'session__session_date'

@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin): # PayslipAdmin (remains the same)
    list_display = ('__str__', 'coach_display_name', 'month', 'year', 'total_amount', 'generated_at', 'generated_by_username', 'file')
    list_filter = ('year', 'month', 'coach', 'generated_by__username')
    search_fields = ('coach__name', 'coach__user__username', 'year')
    readonly_fields = ('coach', 'month', 'year', 'total_amount', 'generated_at', 'generated_by', 'file')
    list_select_related = ('coach', 'coach__user', 'generated_by')
    def coach_display_name(self, obj): return str(obj.coach)
    coach_display_name.short_description = 'Coach'
    def generated_by_username(self, obj): return obj.generated_by.username if obj.generated_by else None
    generated_by_username.short_description = 'Generated By'
    def get_queryset(self, request): return super().get_queryset(request).select_related('coach', 'coach__user', 'generated_by')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return request.user.is_superuser
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser

@admin.register(CoachSessionCompletion) 
class CoachSessionCompletionAdmin(admin.ModelAdmin): # CoachSessionCompletionAdmin (remains the same)
    list_display = ('coach', 'session_display', 'assessments_submitted', 'confirmed_for_payment', 'last_updated')
    list_filter = ('session__session_date', 'coach__name', 'assessments_submitted', 'confirmed_for_payment')
    search_fields = ('coach__name', 'session__school_group__name')
    list_select_related = ('coach', 'session', 'session__school_group')
    readonly_fields = ('last_updated',); fields = ('coach', 'session', 'assessments_submitted', 'confirmed_for_payment', 'last_updated') 
    def session_display(self, obj): return str(obj.session)
    session_display.short_description = 'Session'; session_display.admin_order_field = 'session__session_date'
