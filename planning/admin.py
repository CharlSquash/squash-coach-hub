# planning/admin.py

from django.contrib import admin
from .models import (
    SchoolGroup, Player, Coach, Drill, Session, TimeBlock,
    ActivityAssignment, SessionAssessment, CourtSprintRecord,
    VolleyRecord, BackwallDriveRecord, MatchResult,
    ManualCourtAssignment # <-- Import the new model
)


# Simple registration for SchoolGroup
admin.site.register(SchoolGroup)

# Customize Player Admin slightly
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('full_name','contact_number', 'parent_contact_number', 'skill_level', 'is_active')
    list_filter = ('skill_level', 'is_active', 'school_groups')
    search_fields = ('first_name', 'last_name')
    filter_horizontal = ('school_groups',)

# Simple registration for Coach
admin.site.register(Coach)

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
class TimeBlockInline(admin.TabularInline): # Or use admin.StackedInline for a different layout
    model = TimeBlock
    extra = 1 # Show 1 empty form for adding a new block by default
    fields = ('start_offset_minutes', 'duration_minutes', 'number_of_courts', 'rotation_interval_minutes', 'block_focus')
    ordering = ('start_offset_minutes',)


# --- Custom Admin for Session (Now defined AFTER TimeBlockInline) ---
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'session_date', 'session_start_time', 'school_group', 'planned_duration_minutes')
    list_filter = ('session_date', 'school_group', 'coaches_attending')
    search_fields = ('notes', 'school_group__name', 'coaches_attending__name')
    date_hierarchy = 'session_date'
    filter_horizontal = ('coaches_attending', 'attendees',)
    # Add the inline class here
    inlines = [TimeBlockInline]

    def save_model(self, request, obj, form, change):
        """
        Override save_model to auto-populate attendees based on school_group.
        'obj' is the Session instance being saved.
        """
        # Save the main Session object instance first using the default process
        super().save_model(request, obj, form, change)

        # Now, handle the attendees based on the selected group
        if obj.school_group:
            # Get active players associated with the selected group
            players_in_group = obj.school_group.players.filter(is_active=True)
            # Set the attendees relationship to these players. 
            # This completely replaces any previous attendees or manual selections.
            obj.attendees.set(players_in_group)
        else:
            # If no school group is selected, clear the attendees list
            # (Alternatively, you could choose to leave manually added attendees if no group is selected)
            obj.attendees.clear()
        # Note: We don't need to call obj.save() again here, 
        # because .set() and .clear() on M2M operate on the relationship directly.
    # --- END OF OVERRIDE ---

    # Helper method for list_display
    @admin.display(description='Attendees')
    def get_attendee_count(self, obj):
        return obj.attendees.count()

# Ensure other models like SchoolGroup, Player etc. are also registered
# admin.site.register(SchoolGroup, SchoolGroupAdmin) # Using class from previous step
# admin.site.register(Player) 



# Simple registration for ActivityAssignment
admin.site.register(ActivityAssignment)

# Simple registration for SessionAssessment
admin.site.register(SessionAssessment)

# Simple registrations for metric/match records
admin.site.register(CourtSprintRecord)
admin.site.register(VolleyRecord)
admin.site.register(BackwallDriveRecord)
admin.site.register(MatchResult)

# Register the ManualCourtAssignment model
admin.site.register(ManualCourtAssignment)

