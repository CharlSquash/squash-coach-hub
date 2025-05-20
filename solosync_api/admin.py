# solosync_api/admin.py
from django.contrib import admin
from .models import (
    SoloDrill,
    SoloRoutine,
    RoutineDrillLink,
    SoloSessionLog,
    SoloSessionMetric,
    SoloDrillCategory
)

# --- Admin Configuration for SoloDrillCategory ---
@admin.register(SoloDrillCategory)
class SoloDrillCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

# --- Configuration for SoloRoutine Admin ---
class RoutineDrillLinkInline(admin.TabularInline):
    model = RoutineDrillLink
    # REMOVED 'metrics_to_collect' from fields
    fields = ['order', 'drill', 'duration_seconds', 'reps_target', 'rest_after_seconds', 'notes']
    extra = 1
    ordering = ['order']
    autocomplete_fields = ['drill'] # Recommended

class SoloRoutineAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'difficulty', 'total_duration_display', 'created_at')
    search_fields = ['name', 'description']
    filter_horizontal = ('assigned_players',)
    inlines = [RoutineDrillLinkInline]
    readonly_fields = ('total_duration_display', 'created_at', 'updated_at')
    list_filter = ('created_by', 'difficulty')

admin.site.register(SoloRoutine, SoloRoutineAdmin)


# --- Configuration for SoloSessionLog Admin ---
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
    search_fields = ('player__user__username', 'routine__name', 'notes')
    readonly_fields = ('id', 'created_at', 'completed_at', 'player', 'routine')
    date_hierarchy = 'completed_at'
    inlines = [SoloSessionMetricInline]

    def get_readonly_fields(self, request, obj=None):
        if obj: return self.readonly_fields + ('physical_difficulty', 'notes')
        return self.readonly_fields

    def get_fields(self, request, obj=None):
        if obj: return ('id', 'player', 'routine', 'completed_at', 'created_at', 'physical_difficulty', 'notes')
        return ('player', 'routine', 'completed_at', 'physical_difficulty', 'notes')


# --- UPDATED SoloDrillAdmin ---
@admin.register(SoloDrill)
class SoloDrillAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'display_categories',
        'participant_type',
        'metric_type',
        'default_duration_seconds',
        'youtube_link_exists',
        'created_by',
        'updated_at'
    )
    list_filter = (
        'categories',
        'participant_type',
        'metric_type',
        'created_by',
        'updated_at'
    )
    search_fields = (
        'name',
        'description',
        'categories__name' # Crucial for autocomplete to find by category
    )
    filter_horizontal = ('categories',)
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'youtube_link')
        }),
        ('Categorization & Type', {
            'fields': ('categories', 'participant_type', 'metric_type')
        }),
        ('Timing & Creation', {
            'fields': ('default_duration_seconds', 'created_by', 'created_at', 'updated_at')
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Categories')
    def display_categories(self, obj):
        return ", ".join([category.name for category in obj.categories.all()])

    @admin.display(description='Has YouTube Link?', boolean=True)
    def youtube_link_exists(self, obj):
        return bool(obj.youtube_link)

# Register SoloSessionMetric using custom class
@admin.register(SoloSessionMetric)
class SoloSessionMetricAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_log_info', 'drill', 'metric_name', 'metric_value')
    list_filter = ('drill__name', 'metric_name', 'session_log__routine__name')
    search_fields = ('metric_name', 'metric_value', 'session_log__player__user__username', 'drill__name')
    list_select_related = ('session_log__player__user', 'drill', 'session_log__routine')

    @admin.display(description='Session Log')
    def session_log_info(self, obj):
        if obj.session_log:
            player_name = 'N/A'
            if obj.session_log.player:
                if hasattr(obj.session_log.player, 'user') and obj.session_log.player.user:
                    player_name = obj.session_log.player.user.username
                elif hasattr(obj.session_log.player, 'name'): # Fallback if player has a name field
                    player_name = obj.session_log.player.name
            return f"Log ID {obj.session_log.id} (Player: {player_name})"
        return None

# admin.site.register(RoutineDrillLink) # Usually keep commented out
