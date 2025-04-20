# planning/admin.py
from django.contrib import admin
# Import all models
from .models import (
    Drill, Coach, Player, SchoolGroup, Session, TimeBlock,
    ActivityAssignment, SessionAssessment, CourtSprintRecord,
    VolleyRecord, BackwallDriveRecord, MatchResult # Added new models
)

@admin.register(Drill)
class DrillAdmin(admin.ModelAdmin): # ... as before ...
    list_display = ('name', 'category', 'duration_minutes'); list_filter = ('category',); search_fields = ('name', 'description')

@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin): # ... as before ...
    search_fields = ('name',)

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'skill_level', 'is_active')
    list_filter = ('skill_level', 'is_active', 'school_groups') # Filter by group
    search_fields = ('first_name', 'last_name')
    list_editable = ('skill_level', 'is_active')
    # Consider adding 'photo' if you want to see/upload it here,
    # though dedicated profile page might be better.

@admin.register(SchoolGroup)
class SchoolGroupAdmin(admin.ModelAdmin): # ... as before ...
    list_display = ('name', 'player_count'); search_fields = ('name', 'description'); filter_horizontal = ('players',)
    def player_count(self, obj): return obj.players.count()
    player_count.short_description = 'Number of Players'

class TimeBlockInline(admin.TabularInline): # ... as before ...
    model = TimeBlock; fields = ('start_offset_minutes', 'duration_minutes', 'number_of_courts', 'rotation_interval_minutes', 'block_focus'); extra = 1; ordering = ('start_offset_minutes',)

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin): # ... as before ...
    list_display = ('__str__', 'school_group', 'date', 'start_time'); list_filter = ('school_group', 'date'); search_fields = ('notes', 'school_group__name'); filter_horizontal = ('coaches_attending', 'attendees')
    inlines = [TimeBlockInline]

@admin.register(ActivityAssignment)
class ActivityAssignmentAdmin(admin.ModelAdmin): # ... as before ...
    list_display = ('get_session_info', 'time_block_info', 'court_number', 'get_activity_name', 'lead_coach', 'duration_minutes', 'order'); list_filter = ('time_block__session__school_group', 'time_block__session__date', 'lead_coach', 'drill'); search_fields = ('custom_activity_name', 'drill__name', 'time_block__block_focus', 'time_block__session__school_group__name')
    def get_session_info(self, obj): session = obj.time_block.session; group_name = session.school_group.name if session.school_group else "N/A"; return f"{group_name} {session.date} @ {session.start_time.strftime('%H:%M')}"
    get_session_info.short_description = 'Session'; get_session_info.admin_order_field = 'time_block__session__date'
    def time_block_info(self, obj): block = obj.time_block; start_time_str = block.block_start_datetime.strftime('%H:%M') if block.block_start_datetime else f"Offset {block.start_offset_minutes}m"; return f"Block @ {start_time_str}"
    time_block_info.short_description = 'Time Block'; time_block_info.admin_order_field = 'time_block__start_offset_minutes'
    def get_activity_name(self, obj): return obj.drill.name if obj.drill else obj.custom_activity_name
    get_activity_name.short_description = 'Activity'

# --- NEW Admin Registrations for Tracking Models ---

@admin.register(SessionAssessment)
class SessionAssessmentAdmin(admin.ModelAdmin):
    list_display = ('player', 'session', 'date_recorded', 'effort_rating', 'focus_rating', 'resilience_rating')
    list_filter = ('session__date', 'player', 'effort_rating', 'focus_rating') # Filter by session date too
    list_select_related = ('player', 'session') # Optimize fetching related objects
    # Make fields editable in list view for quick updates?
    # list_editable = ('effort_rating', 'focus_rating', 'resilience_rating', 'composure_rating', 'decision_making_rating')
    search_fields = ('player__first_name', 'player__last_name', 'session__school_group__name', 'coach_notes')
    # Use raw_id_fields if player/session lists get very long
    # raw_id_fields = ('player', 'session')

@admin.register(CourtSprintRecord)
class CourtSprintRecordAdmin(admin.ModelAdmin):
    list_display = ('player', 'date_recorded', 'duration_choice', 'score', 'session')
    list_filter = ('date_recorded', 'duration_choice', 'player')
    list_select_related = ('player', 'session')
    search_fields = ('player__first_name', 'player__last_name', 'score')

@admin.register(VolleyRecord)
class VolleyRecordAdmin(admin.ModelAdmin):
    list_display = ('player', 'date_recorded', 'shot_type', 'consecutive_count', 'session')
    list_filter = ('date_recorded', 'shot_type', 'player')
    list_select_related = ('player', 'session')
    search_fields = ('player__first_name', 'player__last_name')

@admin.register(BackwallDriveRecord)
class BackwallDriveRecordAdmin(admin.ModelAdmin):
    list_display = ('player', 'date_recorded', 'shot_type', 'consecutive_count', 'session')
    list_filter = ('date_recorded', 'shot_type', 'player')
    list_select_related = ('player', 'session')
    search_fields = ('player__first_name', 'player__last_name')

@admin.register(MatchResult)
class MatchResultAdmin(admin.ModelAdmin):
    list_display = ('player', 'date', 'opponent_name', 'player_score_str', 'is_competitive', 'session')
    list_filter = ('date', 'is_competitive', 'player')
    list_select_related = ('player', 'session')
    search_fields = ('player__first_name', 'player__last_name', 'opponent_name', 'match_notes')
    list_editable = ('is_competitive',)