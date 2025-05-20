# solosync_api/models.py
from django.db import models
from django.conf import settings # To reference your project's User model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
# Imports needed for calculated duration property
from django.db.models import Sum, F, Value, IntegerField
from django.db.models.functions import Coalesce

# Ensure settings.AUTH_USER_MODEL points to your actual User model


# --- NEW MODEL: SoloDrillCategory ---
class SoloDrillCategory(models.Model):
    """
    Represents a category for SoloDrills, e.g., Racketwork, Fitness, Ghosting.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="e.g., Racketwork, Fitness, Stretching & Warmup, Ghosting, Pressure Drills"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description of the category."
    )

    class Meta:
        verbose_name = "Solo Drill Category"
        verbose_name_plural = "Solo Drill Categories"
        ordering = ['name'] # Optional: Default ordering for categories

    def __str__(self):
        return self.name

# --- UPDATED SoloDrill model ---
class SoloDrill(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True) # Changed from blank=True to blank=True, null=True for consistency
    # metrics_definition = models.JSONField(default=dict, blank=True, help_text="Defines potential metrics and their types") # This field will be replaced by metric_type
    youtube_link = models.URLField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Optional YouTube link for drill explanation/demonstration."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='created_solo_drills',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- NEW FIELDS based on the plan ---
    categories = models.ManyToManyField(
        SoloDrillCategory,
        blank=True,
        related_name='solo_drills',
        help_text="Categories this drill belongs to (e.g., Fitness, Ghosting)."
    )

    PARTICIPANT_CHOICES = [
        ('SOLO', 'Solo (Player Only)'),
        ('COACH_PLAYER', 'Coach + Player(s)'),
        ('ANY', 'Any (Flexible)')
    ]
    participant_type = models.CharField(
        max_length=20,
        choices=PARTICIPANT_CHOICES,
        default='SOLO', # Defaulting to SOLO as per original plan for SoloDrills
        help_text="Intended participant setup for this drill when used in a routine."
    )

    METRIC_TYPE_CHOICES = [
        ('AMOUNT', 'Amount (e.g., count, repetitions)'),
        ('TIME', 'Time to Complete (e.g., duration for a set task)')
        # Add ('NONE', 'No Specific Metric') if you want an explicit "none" option,
        # otherwise blank=True, null=True handles cases with no metric.
    ]
    metric_type = models.CharField(
        max_length=10,
        choices=METRIC_TYPE_CHOICES,
        blank=True,  # Allows this field to be empty if no specific metric
        null=True,   # Stores NULL in the database if empty
        help_text="The type of metric collected for this drill, if any."
    )
    # Note: The old 'metrics_definition' JSONField has been removed/commented out.
    # If you need to migrate data from 'metrics_definition' to 'metric_type',
    # a custom data migration will be needed after applying schema migrations.

    # Added default_duration_seconds field
    default_duration_seconds = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Suggested default duration for this drill in seconds, if applicable (e.g., for timed drills)."
    )


    class Meta:
        ordering = ['name'] # Optional: Default ordering for drills

    def __str__(self):
        return self.name

class SoloRoutine(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='created_solo_routines',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    assigned_players = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='assigned_solo_routines',
        blank=True,
        help_text="Players assigned to perform this routine"
    )

    # *** NEW: Difficulty Rating Field ***
    class DifficultyChoices(models.IntegerChoices):
        VERY_EASY = 1, '1 - Very Easy'
        EASY = 2, '2 - Easy'
        MEDIUM = 3, '3 - Medium'
        HARD = 4, '4 - Hard'
        VERY_HARD = 5, '5 - Very Hard'

    difficulty = models.PositiveSmallIntegerField(
        choices=DifficultyChoices.choices,
        null=True, blank=True, # Optional for existing routines
        help_text="Coach's rating of the routine difficulty (1-5)"
    )
    # *** END Difficulty Rating Field ***

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    drills = models.ManyToManyField(
        SoloDrill,
        through='RoutineDrillLink',
        related_name='routines_included_in'
    )
    # --- Stored total_duration_minutes field REMOVED ---

    class Meta:
        ordering = ['name']

    # --- calculate_total_duration method REMOVED ---
    # --- overridden save method REMOVED ---

    # *** NEW: Calculated Total Duration Property ***
    @property
    def total_duration_seconds(self):
        """Calculates total duration (drill time + rest time after each drill) in seconds."""
        if not self.pk or not hasattr(self, 'routinedrilllink_set'):
            # If the routine hasn't been saved yet or somehow lacks the related manager
            return 0

        # Aggregate the sum of duration and rest, treating nulls as 0
        total_data = self.routinedrilllink_set.aggregate(
            total_duration=Sum(Coalesce(F('duration_seconds'), Value(0), output_field=IntegerField())),
            total_rest=Sum(Coalesce(F('rest_after_seconds'), Value(0), output_field=IntegerField()))
        )

        total_duration = total_data.get('total_duration') or 0
        total_rest = total_data.get('total_rest') or 0

        # This calculation includes rest *after* the last drill.
        # Adjust if different logic is needed (e.g., only sum drill durations).
        return total_duration + total_rest

    # *** NEW: Helper method for display format ***
    def total_duration_display(self):
        """Formats total_duration_seconds into MM:SS string."""
        total_seconds = self.total_duration_seconds
        if total_seconds <= 0:
            return "0:00"
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}" # e.g., "5:03", "12:30"
    # Make this method callable from admin list_display
    total_duration_display.short_description = 'Total Duration (MM:SS)'

    def __str__(self):
        creator = f" (by {self.created_by.username})" if self.created_by else ""
        # Optionally include difficulty display in __str__
        difficulty_str = f" [Diff: {self.get_difficulty_display()}]" if self.difficulty else ""
        return f"{self.name}{creator}{difficulty_str} ({self.total_duration_display()})"


class RoutineDrillLink(models.Model):
    """Defines a specific drill's place and settings within a routine."""

    routine = models.ForeignKey(SoloRoutine, on_delete=models.CASCADE, related_name='routinedrilllink_set')
    drill = models.ForeignKey(SoloDrill, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(help_text="Sequence number (1, 2, 3...)")

    duration_seconds = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(1)],
        help_text="Time for this specific drill step (seconds)."
    )
    reps_target = models.PositiveIntegerField(null=True, blank=True, help_text="Target repetitions")
    rest_after_seconds = models.PositiveIntegerField(default=30, help_text="Rest duration after this drill (seconds)")
    # metrics_to_collect = models.JSONField(default=list, blank=True, help_text="List of metric keys to log for this step") # <-- REMOVED
    notes = models.TextField(blank=True, help_text="Optional notes for the player for this specific step")

    class Meta:
        ordering = ['routine', 'order']
        unique_together = ('routine', 'order')

    def __str__(self):
        return f"{self.routine.name} - Step {self.order}: {self.drill.name}"



class SoloSessionLog(models.Model):
    """Records a completed solo session by a player."""
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='solo_session_logs',
        on_delete=models.CASCADE
    )
    routine = models.ForeignKey(
        SoloRoutine,
        related_name='session_logs',
        on_delete=models.CASCADE # Consider SET_NULL if routines can be deleted but logs kept
    )

    # *** REVERTED Field Names back to originals ***
    completed_at = models.DateTimeField(
        default=timezone.now, # Use timezone.now default here
        db_index=True,
        help_text="Timestamp when the session log was submitted" # Updated help text
    )
    physical_difficulty = models.PositiveSmallIntegerField( # Use PositiveSmallIntegerField for 1-5
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True, # Keep optional (allow skipping survey part?)
        help_text="Player rating (1-5) of physical difficulty"
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional overall player notes for the session"
    )
    # *** END REVERTED Field Names ***

    created_at = models.DateTimeField(auto_now_add=True) # Keep track of record creation

    class Meta:
        ordering = ['-completed_at'] # Order by completion date

    def __str__(self):
        player_name = self.player.username
        routine_name = self.routine.name if self.routine else "Unknown Routine"
        date_str = self.completed_at.strftime('%Y-%m-%d %H:%M') if self.completed_at else "Unknown Date"
        return f"Session by {player_name} - {routine_name} ({date_str})"


class SoloSessionMetric(models.Model):
    """Stores an individual metric value logged during a session."""
    # Keep this model as it was, seems okay
    session_log = models.ForeignKey(
        SoloSessionLog,
        related_name='logged_metrics',
        on_delete=models.CASCADE
    )
    drill = models.ForeignKey(
        SoloDrill,
        related_name='logged_metric_instances',
        on_delete=models.CASCADE
    )
    metric_name = models.CharField(max_length=50, help_text="e.g., 'reps', 'target_hits'")
    metric_value = models.CharField(max_length=100, help_text="Logged value (stored as string for flexibility)")

    class Meta:
        indexes = [
            models.Index(fields=['session_log', 'drill']),
        ]

    def __str__(self):
        log_id = self.session_log.id if self.session_log else 'N/A'
        drill_name = self.drill.name if self.drill else 'N/A'
        return f"Metric for Log {log_id} - {drill_name} - {self.metric_name}: {self.metric_value}"