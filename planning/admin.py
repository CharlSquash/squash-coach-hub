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
    list_display = ('full_name', 'skill_level', 'is_active')
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
    list_display = ('__str__', 'date', 'start_time', 'school_group', 'planned_duration_minutes')
    list_filter = ('date', 'school_group', 'coaches_attending')
    search_fields = ('notes', 'school_group__name', 'coaches_attending__name')
    date_hierarchy = 'date'
    filter_horizontal = ('coaches_attending', 'attendees',)
    # Add the inline class here
    inlines = [TimeBlockInline]


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

