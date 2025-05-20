# planning/admin.py
from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html # For user_link in CoachAdmin

# Import User model - ENSURE THIS IMPORT IS PRESENT AND CORRECT
from django.contrib.auth import get_user_model

# Import your models
from .models import (
    SchoolGroup, Player, Coach, Drill, Session, TimeBlock,
    ActivityAssignment, SessionAssessment, CourtSprintRecord, # SessionAssessment is key here
    VolleyRecord, BackwallDriveRecord, MatchResult,
    ManualCourtAssignment, CoachAvailability, Payslip
)

# Import the service functions
from .payslip_services import create_all_payslips_for_period
# generate_payslip_for_single_coach will be imported locally in the admin action


# Get the User model once, after importing get_user_model
User = get_user_model()


# --- Form for Payslip Generation ---
class PeriodCoachSelectionForm(forms.Form):
    """
    Form for selecting the year, month, force_regeneration option,
    and optionally a specific coach for payslip generation.
    """
    year = forms.IntegerField(
        label="Year",
        initial=timezone.now().year,
        help_text="Enter the year for payslip generation (e.g., 2025)."
    )
    month = forms.IntegerField(
        label="Month",
        min_value=1,
        max_value=12,
        initial=timezone.now().month,
        help_text="Enter the month for payslip generation (1-12)."
    )
    specific_coach = forms.ModelChoiceField(
        queryset=Coach.objects.filter(is_active=True), # Show only active coaches
        required=False, # Make this field optional
        label="Specific Coach (Optional)",
        help_text="Leave blank to generate for ALL eligible active coaches. Select a coach to generate only for them.",
        # widget=forms.Select(attrs={'class': 'select2-widget'}) # Optional: for better UI if you use django-select2
    )
    force_regeneration = forms.BooleanField(
        label="Force Regeneration",
        required=False,
        initial=False,
        help_text="If checked, any existing payslip for the selected coach(es) and period will be deleted and regenerated."
    )


# --- Existing Admin Registrations (Preserved) ---

# Simple registration for SchoolGroup
admin.site.register(SchoolGroup)

# Customize Player Admin slightly
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('full_name','contact_number', 'parent_contact_number', 'skill_level', 'is_active')
    list_filter = ('skill_level', 'is_active', 'school_groups')
    search_fields = ('first_name', 'last_name')
    filter_horizontal = ('school_groups',)

# --- Custom Admin for Coach (UPDATED with Payslip Action) ---
@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_link', 'email', 'phone', 'is_active', 'hourly_rate')
    search_fields = ('name', 'email', 'user__username', 'user__first_name', 'user__last_name')
    list_filter = ('is_active', 'user')
    fields = ('user', 'name', 'phone', 'email', 'is_active', 'hourly_rate')
    raw_id_fields = ('user',)
    actions = ['trigger_payslip_generation_action']

    @admin.display(description='Linked User Account')
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return "-"
    user_link.admin_order_field = 'user__username'

    def trigger_payslip_generation_action(self, request, queryset):
        # This method handles both the initial display of the form
        # and the processing of the submitted form.

        print(f"\n--- trigger_payslip_generation_action CALLED. Method: {request.method} ---")
        print(f"--- Raw request.POST data: {request.POST} ---")

        from .payslip_services import generate_payslip_for_single_coach

        # Check if our custom form's submit button ("process_payslips") was pressed.
        # This indicates the user has submitted the intermediate form.
        if request.method == 'POST' and 'process_payslips' in request.POST:
            print("--- 'process_payslips' KEY FOUND in request.POST. Attempting to process the submitted form. ---")
            form = PeriodCoachSelectionForm(request.POST) # Bind form to the submitted data

            if form.is_valid():
                print(f"--- Form IS VALID. Cleaned data: {form.cleaned_data} ---")
                year = form.cleaned_data['year']
                month = form.cleaned_data['month']
                force = form.cleaned_data['force_regeneration']
                selected_coach_instance = form.cleaned_data.get('specific_coach')
                generating_user_id = request.user.id if request.user.is_authenticated else None

                if selected_coach_instance:
                    self.message_user(request, f"Starting payslip generation for {selected_coach_instance} for {month:02}/{year}...", messages.INFO)
                    print(f"--- Calling generate_payslip_for_single_coach for coach ID {selected_coach_instance.id} ---")
                    result = generate_payslip_for_single_coach(
                        coach_id=selected_coach_instance.id, year=year, month=month,
                        generating_user_id=generating_user_id, force_regeneration=force
                    )
                    print(f"--- Result from single coach: {result} ---")
                    if result.get('status') == 'success': self.message_user(request, result.get('message', 'Payslip generated successfully.'), messages.SUCCESS)
                    elif result.get('status') == 'skipped': self.message_user(request, result.get('message', 'Payslip skipped.'), messages.WARNING)
                    else: self.message_user(request, result.get('message', 'An error occurred.'), messages.ERROR)
                    if result.get('details'):
                        for detail_msg in result['details']: self.message_user(request, detail_msg, messages.INFO)

                else: # No specific coach selected, process for all
                    self.message_user(request, f"Starting payslip generation for {month:02}/{year} for ALL eligible coaches...", messages.INFO)
                    print("--- Calling create_all_payslips_for_period ---")
                    result = create_all_payslips_for_period(
                        year=year, month=month,
                        generating_user_id=generating_user_id, force_regeneration=force
                    )
                    print(f"--- Result from all coaches: {result} ---")
                    if result.get('summary_message'):
                        if result.get('error_count', 0) > 0 or (result.get('generated_count', 0) == 0 and result.get('skipped_count',0) > 0): self.message_user(request, result['summary_message'], messages.WARNING)
                        elif result.get('generated_count', 0) > 0: self.message_user(request, result['summary_message'], messages.SUCCESS)
                        else: self.message_user(request, result['summary_message'], messages.INFO)
                    if result.get('details'):
                        for detail_msg in result['details']:
                            if detail_msg != result.get('summary_message') and not detail_msg.startswith("Starting payslip generation"): self.message_user(request, detail_msg, messages.INFO)
                
                return HttpResponseRedirect(request.get_full_path()) # Redirect after successful processing
            else:
                # Form was submitted but is invalid
                print(f"--- Form SUBMITTED but IS INVALID. Errors (JSON): {form.errors.as_json()} ---")
                self.message_user(request, "Form is invalid. Please correct the errors displayed on the form.", messages.ERROR)
        
        else:
            if request.method == 'POST':
                print("--- Initial POST from admin action (no 'process_payslips'). Displaying form. ---")
            else: # GET request
                print("--- GET request. Displaying form. ---")
            form = PeriodCoachSelectionForm() 

        context = {
            **self.admin_site.each_context(request),
            'title': 'Generate Payslip(s) for Period',
            'form': form, 
            'opts': self.model._meta,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME, 
            'queryset': queryset, 
        }
        print(f"--- Rendering template 'admin/payslip_generation_form_template.html'. Form has errors: {bool(form.errors)} ---")
        return render(request, 'admin/payslip_generation_form_template.html', context)

    trigger_payslip_generation_action.short_description = "Generate Payslip(s) for Period"


# Custom Admin for Drill model
@admin.register(Drill)
class DrillAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'duration_minutes_default',
        'ideal_num_players',
        'suitable_for_any'
    )
    list_filter = ('suitable_for_any',)
    search_fields = ('name', 'description')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'duration_minutes_default')
        }),
        ('Player Suitability', {
            'fields': ('ideal_num_players', 'suitable_for_any')
        }),
    )

# --- Define Inline Admin for TimeBlock FIRST ---
class TimeBlockInline(admin.TabularInline):
    model = TimeBlock
    extra = 1
    fields = ('start_offset_minutes', 'duration_minutes', 'number_of_courts', 'rotation_interval_minutes', 'block_focus')
    ordering = ('start_offset_minutes',)


# --- Custom Admin for Session (UPDATED) ---
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        '__str__',
        'session_date',
        'session_start_time',
        'school_group',
        'venue_name', 
        'planned_duration_minutes',
        'get_assigned_coaches_display',
        'is_cancelled', 
        'assessments_complete' 
    )
    list_filter = (
        'session_date',
        'is_cancelled', 
        'venue_name',   
        'school_group',
        'coaches_attending',
        'assessments_complete'
    )
    search_fields = (
        'notes',
        'school_group__name',
        'venue_name',   
        'coaches_attending__name'
    )
    date_hierarchy = 'session_date'
    filter_horizontal = ('coaches_attending', 'attendees',) 
    # inlines = [TimeBlockInline] # Uncomment if TimeBlockInline is defined and used
    readonly_fields = ('assessments_complete',) 
    fields = (
        'school_group',
        'session_date',
        'session_start_time',
        'planned_duration_minutes',
        'venue_name',       
        'is_cancelled',     
        'coaches_attending',
        'attendees',
        'notes',
        'assessments_complete'
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.school_group and (not change or (change and not Session.objects.get(pk=obj.pk).school_group)):
            players_in_group = obj.school_group.players.filter(is_active=True)
            obj.attendees.set(players_in_group)

    @admin.display(description='Assigned Coaches')
    def get_assigned_coaches_display(self, obj):
        return ", ".join([coach.name for coach in obj.coaches_attending.all()])


# Simple registration for ActivityAssignment
admin.site.register(ActivityAssignment)

# --- UPDATED SessionAssessmentAdmin ---
@admin.register(SessionAssessment)
class SessionAssessmentAdmin(admin.ModelAdmin):
    """
    Admin interface options for SessionAssessment model.
    """
    list_display = (
        'player',
        'session_date_display',
        'submitted_by_user', # Custom method to display user
        'effort_rating',
        'focus_rating',
        'is_hidden', # New field
        'date_recorded'
    )
    list_filter = (
        'session__session_date',
        'player',
        'submitted_by',
        'is_hidden', # New filter
        'effort_rating',
        'focus_rating'
    )
    search_fields = (
        'player__first_name',
        'player__last_name',
        'session__school_group__name', # Assuming Session links to SchoolGroup
        'submitted_by__username',
        'submitted_by__first_name',
        'submitted_by__last_name',
        'coach_notes'
    )
    readonly_fields = ('date_recorded',) # 'submitted_by' could also be readonly after creation

    fieldsets = (
        (None, {
            'fields': ('player', 'session', 'submitted_by')
        }),
        ('Ratings', {
            'fields': ('effort_rating', 'focus_rating', 'resilience_rating', 'composure_rating', 'decision_making_rating')
        }),
        ('Notes & Visibility', {
            'fields': ('coach_notes', 'is_hidden') # Add is_hidden here
        }),
        ('Metadata', {
            'fields': ('date_recorded',),
            'classes': ('collapse',) 
        }),
    )

    def session_date_display(self, obj):
        if obj.session:
            return obj.session.session_date
        return None
    session_date_display.short_description = 'Session Date'
    session_date_display.admin_order_field = 'session__session_date'

    def submitted_by_user(self, obj):
        if obj.submitted_by:
            return obj.submitted_by.get_full_name() or obj.submitted_by.username
        return None
    submitted_by_user.short_description = 'Assessed By'
    submitted_by_user.admin_order_field = 'submitted_by'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None: 
            if request.user.is_staff:
                form.base_fields['submitted_by'].initial = request.user
                if 'submitted_by' in form.base_fields: # Check if field exists
                    form.base_fields['submitted_by'].widget.attrs['disabled'] = True 
        else: 
            if 'submitted_by' in form.base_fields: # Check if field exists
                form.base_fields['submitted_by'].widget.attrs['disabled'] = True

        if not request.user.is_superuser:
            if 'is_hidden' in form.base_fields:
                form.base_fields['is_hidden'].disabled = True
        return form

    def save_model(self, request, obj, form, change):
        if not obj.pk: 
            obj.submitted_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if not obj: 
            return super().has_change_permission(request, obj)
        if request.user.is_superuser:
            return True
        if obj.submitted_by == request.user:
            return True
        return False 

    def has_delete_permission(self, request, obj=None):
        if not obj: 
            return super().has_delete_permission(request, obj)
        if request.user.is_superuser:
            return True
        if obj.submitted_by == request.user:
            return True
        return False 

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs 
        return qs.filter(is_hidden=False)
# --- END UPDATED SessionAssessmentAdmin ---


# Simple registrations for metric/match records
admin.site.register(CourtSprintRecord)
admin.site.register(VolleyRecord)
admin.site.register(BackwallDriveRecord)
admin.site.register(MatchResult)

# Register the ManualCourtAssignment model
admin.site.register(ManualCourtAssignment)

# --- Register CoachAvailability ---
@admin.register(CoachAvailability)
class CoachAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('coach_username', 'session_display', 'is_available', 'timestamp')
    list_filter = ('is_available', 'session__session_date', 'coach')
    search_fields = ('coach__user__username', 'session__school_group__name', 'notes')
    list_select_related = ('coach', 'coach__user', 'session', 'session__school_group')
    readonly_fields = ('timestamp',)
    fields = ('coach', 'session', 'is_available', 'notes', 'timestamp')
    raw_id_fields = ('coach', 'session',)

    @admin.display(description='Coach', ordering='coach__user__username')
    def coach_username(self, obj):
        return obj.coach.user.username if obj.coach and obj.coach.user else obj.coach.name

    @admin.display(description='Session', ordering='session__session_date')
    def session_display(self, obj):
        return str(obj.session)


# --- Custom Admin for Payslip (UPDATED) ---
@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'coach_display_name', 'month', 'year', 'total_amount', 'generated_at', 'generated_by_username', 'file')
    list_filter = ('year', 'month', 'coach', 'generated_by__username')
    search_fields = ('coach__name', 'coach__user__username', 'year')
    readonly_fields = ('coach', 'month', 'year', 'total_amount', 'generated_at', 'generated_by', 'file')
    list_select_related = ('coach', 'coach__user', 'generated_by')

    @admin.display(description='Coach', ordering='coach__name')
    def coach_display_name(self, obj):
        return str(obj.coach)

    @admin.display(description='Generated By', ordering='generated_by__username')
    def generated_by_username(self, obj):
        return obj.generated_by.username if obj.generated_by else None

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('coach', 'coach__user', 'generated_by')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
