# solosync_api/admin.py
from django.contrib import admin
from .models import (
    SoloDrill,
    SoloRoutine,
    RoutineDrillLink,
    SoloSessionLog,
    SoloSessionMetric
)

# --- Configuration for SoloRoutine Admin ---
# (Keep existing RoutineDrillLinkInline and SoloRoutineAdmin as they were in Message #171)
class RoutineDrillLinkInline(admin.TabularInline):
    model = RoutineDrillLink
    fields = ['order', 'drill', 'duration_seconds', 'reps_target', 'rest_after_seconds', 'metrics_to_collect', 'notes']
    extra = 1
    ordering = ['order']
    # autocomplete_fields = ['drill'] # Optional

class SoloRoutineAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'difficulty', 'total_duration_display', 'created_at')
    search_fields = ['name', 'description']
    filter_horizontal = ('assigned_players',)
    inlines = [RoutineDrillLinkInline]
    readonly_fields = ('total_duration_display', 'created_at', 'updated_at')
    list_filter = ('created_by', 'difficulty')


# --- Configuration for SoloSessionLog Admin ---
# (Keep existing SoloSessionMetricInline and SoloSessionLogAdmin as they were in Message #171)
class SoloSessionMetricInline(admin.TabularInline):
    model = SoloSessionMetric
    extra = 0
    readonly_fields = ('drill', 'metric_name', 'metric_value')
    fields = ('drill', 'metric_name', 'metric_value')
    can_delete = False
    max_num = 0

@admin.register(SoloSessionLog)
class SoloSessionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'player', 'routine', 'completed_at', 'physical_difficulty')
    list_filter = ('player', 'routine', 'completed_at')
    search_fields = ('player__username', 'routine__name', 'notes')
    readonly_fields = ('id', 'created_at', 'completed_at', 'player', 'routine')
    date_hierarchy = 'completed_at'
    inlines = [SoloSessionMetricInline]

    def get_readonly_fields(self, request, obj=None):
        if obj: return self.readonly_fields + ('physical_difficulty', 'notes')
        return self.readonly_fields

    def get_fields(self, request, obj=None):
        if obj: return ('id', 'player', 'routine', 'completed_at', 'created_at', 'physical_difficulty', 'notes')
        return ('player', 'routine', 'completed_at', 'physical_difficulty', 'notes')


# --- Register Remaining Models ---

# *** MODIFIED SoloDrillAdmin ***
@admin.register(SoloDrill)
class SoloDrillAdmin(admin.ModelAdmin):
     # Added a helper display method for the link status
     list_display = ('id', 'name', 'youtube_link_exists', 'created_by', 'updated_at')
     search_fields = ('name', 'description')
     list_filter = ('created_by',)

     # Use fieldsets to organize the add/change form and include the new link field
     fieldsets = (
         (None, { # No section title for the main fields
             'fields': ('name', 'description')
         }),
         ('Drill Details', { # Separate section for details
             'fields': ('metrics_definition', 'youtube_link') # Added youtube_link here
         }),
         ('Metadata', { # Optional section for metadata
             'fields': ('created_by',), # Assuming created_by is editable or set elsewhere
             # Add 'created_at', 'updated_at' here if you want them visible but non-editable
             # 'classes': ('collapse',), # Optionally collapse this section
         }),
     )
     # Add fields here that are automatically set and shouldn't be edited on the form
     # readonly_fields = ('created_at', 'updated_at') # Uncomment if you want them visible

     # Helper method to show True/False in list view if link exists
     @admin.display(description='Has YouTube Link?', boolean=True)
     def youtube_link_exists(self, obj):
         return bool(obj.youtube_link)
# *** END MODIFIED SoloDrillAdmin ***


# Register SoloRoutine using the custom SoloRoutineAdmin class
admin.site.register(SoloRoutine, SoloRoutineAdmin)


# Register SoloSessionMetric using custom class (Keep as is)
@admin.register(SoloSessionMetric)
class SoloSessionMetricAdmin(admin.ModelAdmin):
    # ... (keep existing SoloSessionMetricAdmin code from Message #171) ...
    list_display = ('id', 'session_log_info', 'drill', 'metric_name', 'metric_value')
    list_filter = ('drill', 'metric_name', 'session_log__routine')
    search_fields = ('metric_name', 'metric_value', 'session_log__player__username', 'drill__name')
    list_select_related = ('session_log__player', 'drill')

    @admin.display(description='Session Log')
    def session_log_info(self, obj):
        if obj.session_log:
            player_display = obj.session_log.player.username if obj.session_log.player else 'N/A'
            return f"Log ID {obj.session_log.id} (Player: {player_display})"
        return None


# admin.site.register(RoutineDrillLink) # Usually keep commented out