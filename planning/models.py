# planning/models.py
# Added ManualCourtAssignment model

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.conf import settings
import datetime

# Consider using settings.AUTH_USER_MODEL if you have a custom user model
User = settings.AUTH_USER_MODEL

# --- Supporting Models ---

class SchoolGroup(models.Model):
    """Represents a group of players, e.g., 'Boys U19 A'."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Player(models.Model):
    """Represents a player."""
    class SkillLevel(models.TextChoices):
        BEGINNER = 'BEG', 'Beginner'
        INTERMEDIATE = 'INT', 'Intermediate'
        ADVANCED = 'ADV', 'Advanced'

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    date_of_birth = models.DateField(null=True, blank=True)
    skill_level = models.CharField(
        max_length=3,
        choices=SkillLevel.choices,
        default=SkillLevel.BEGINNER,
        blank=True
    )
    school_groups = models.ManyToManyField(
        SchoolGroup,
        related_name='players',
        blank=True
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='player_photos/', null=True, blank=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name

    class Meta:
        ordering = ['last_name', 'first_name']


class Coach(models.Model):
    """Represents a coach."""
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Drill(models.Model):
    """Represents a reusable drill or activity."""
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    duration_minutes_default = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1)],
        help_text="Default duration in minutes when adding to a session."
    )

    PLAYER_COUNT_CHOICES = [
        (1, '1 Player'),
        (2, '2 Players'),
        (3, '3 Players'),
        (4, '4+ Players'),
    ]
    ideal_num_players = models.IntegerField(
        choices=PLAYER_COUNT_CHOICES,
        null=True,
        blank=True,
        help_text="Ideal number of players for this drill (if not suitable for any number)."
    )
    suitable_for_any = models.BooleanField(
        default=False,
        help_text="Check if this drill works well regardless of the specific number of players."
    )

    def __str__(self):
        return self.name

# --- Session Planning Models ---

class Session(models.Model):
    """Represents a single training session."""
    date = models.DateField(default=timezone.now)
    start_time = models.TimeField(default=datetime.time(15, 0))
    planned_duration_minutes = models.PositiveIntegerField(default=60)
    school_group = models.ForeignKey(
        SchoolGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions'
    )
    coaches_attending = models.ManyToManyField(
        Coach,
        related_name='sessions_coaching',
        blank=True
    )
    notes = models.TextField(blank=True, help_text="Overall session objectives or notes.")
    attendees = models.ManyToManyField(
        Player,
        related_name='sessions_attended',
        blank=True
    )

    @property
    def end_time(self):
        if self.start_time and self.planned_duration_minutes:
            start_dt = datetime.datetime.combine(self.date, self.start_time)
            if settings.USE_TZ and timezone.is_naive(start_dt):
                 start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
            elif not settings.USE_TZ and timezone.is_aware(start_dt):
                 start_dt = timezone.make_naive(start_dt, timezone.get_current_timezone())
            try:
                end_dt = start_dt + datetime.timedelta(minutes=self.planned_duration_minutes)
                return end_dt.time()
            except TypeError:
                return None
        return None

    def __str__(self):
        group_name = self.school_group.name if self.school_group else "General"
        return f"{group_name} Session on {self.date.strftime('%Y-%m-%d')} at {self.start_time.strftime('%H:%M')}"

    class Meta:
        ordering = ['-date', '-start_time']


class TimeBlock(models.Model):
    """Represents a segment of time within a Session."""
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='time_blocks')
    start_offset_minutes = models.PositiveIntegerField(default=0, help_text="Minutes from session start time.")
    duration_minutes = models.PositiveIntegerField(default=15, validators=[MinValueValidator(1)])
    number_of_courts = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    rotation_interval_minutes = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1)],
        help_text="Optional: Rotate players between courts every X minutes within this block."
    )
    block_focus = models.CharField(max_length=200, blank=True, help_text="Specific focus for this time block (e.g., Forehand Drives, Match Play).")

    @property
    def block_start_datetime(self):
        """Calculate the absolute start datetime of the block."""
        if self.session.start_time:
            start_dt = datetime.datetime.combine(self.session.date, self.session.start_time)
            if settings.USE_TZ and timezone.is_naive(start_dt):
                 start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
            elif not settings.USE_TZ and timezone.is_aware(start_dt):
                 start_dt = timezone.make_naive(start_dt, timezone.get_current_timezone())
            try:
                 return start_dt + datetime.timedelta(minutes=int(self.start_offset_minutes))
            except (TypeError, ValueError):
                return None
        return None

    @property
    def block_end_datetime(self):
        """Calculate the absolute end datetime of the block."""
        start = self.block_start_datetime
        if start and self.duration_minutes:
            try:
                return start + datetime.timedelta(minutes=int(self.duration_minutes))
            except (TypeError, ValueError):
                return None
        return None

    def __str__(self):
        start_time_str = self.block_start_datetime.strftime('%H:%M') if self.block_start_datetime else '?:??'
        return f"Block in {self.session} starting ~{start_time_str} ({self.duration_minutes} min)"

    class Meta:
        ordering = ['session', 'start_offset_minutes']


class ActivityAssignment(models.Model):
    """Assigns a Drill or custom activity to a court within a TimeBlock."""
    time_block = models.ForeignKey(TimeBlock, on_delete=models.CASCADE, related_name='activities')
    court_number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    drill = models.ForeignKey(Drill, on_delete=models.SET_NULL, null=True, blank=True)
    custom_activity_name = models.CharField(
        max_length=150, blank=True,
        help_text="Use this if not selecting a pre-defined Drill."
    )
    duration_minutes = models.PositiveIntegerField(
        default=10, validators=[MinValueValidator(1)],
        help_text="Estimated duration for this specific activity."
    )
    lead_coach = models.ForeignKey(
        Coach, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='led_activities'
    )
    order = models.PositiveIntegerField(default=0, help_text="Order of activity within the court/block (0 first).")
    activity_notes = models.TextField(blank=True, help_text="Specific notes for this activity instance.")

    def __str__(self):
        activity_name = self.drill.name if self.drill else self.custom_activity_name
        return f"{activity_name} on Court {self.court_number} in {self.time_block}"

    class Meta:
        ordering = ['time_block', 'court_number', 'order']


# --- NEW MODEL for Manual Assignments ---
class ManualCourtAssignment(models.Model):
    """Stores a specific manual assignment of a player to a court for a time block."""
    time_block = models.ForeignKey(TimeBlock, on_delete=models.CASCADE, related_name='manual_assignments')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='manual_assignments')
    court_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    # Add timestamp for tracking when assignment was made/updated
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.player} on Court {self.court_number} during {self.time_block}"

    class Meta:
        # Ensure a player is only assigned to one court per time block
        unique_together = ('time_block', 'player')
        ordering = ['time_block', 'court_number', 'player__last_name']

# --- Player Tracking Models ---

class SessionAssessment(models.Model):
    """Coach's assessment of a player for a specific session."""
    class Rating(models.IntegerChoices):
        POOR = 1, 'Poor'
        BELOW_AVERAGE = 2, 'Below Average'
        AVERAGE = 3, 'Average'
        GOOD = 4, 'Good'
        EXCELLENT = 5, 'Excellent'

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='session_assessments')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='session_assessments')
    date_recorded = models.DateField(default=timezone.now)
    effort_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    focus_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    resilience_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    composure_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    decision_making_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    coach_notes = models.TextField(blank=True)

    def __str__(self):
        return f"Assessment for {self.player} in {self.session}"

    class Meta:
        unique_together = ('session', 'player')
        ordering = ['-date_recorded', 'player__last_name']


class CourtSprintRecord(models.Model):
    """Record of a player's court sprint test result."""
    class DurationChoice(models.TextChoices):
        THREE_MIN = '3m', '3 Minutes'
        FIVE_MIN = '5m', '5 Minutes'
        TEN_MIN = '10m', '10 Minutes'

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='sprint_records')
    date_recorded = models.DateField(default=timezone.now)
    duration_choice = models.CharField(max_length=3, choices=DurationChoice.choices)
    score = models.PositiveIntegerField(help_text="Number of full court lengths completed.")
    session = models.ForeignKey(
        Session, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sprint_tests_conducted',
        help_text="Optional: Link to the session where the test was done."
    )

    def __str__(self):
        return f"Sprint ({self.get_duration_choice_display()}) for {self.player} on {self.date_recorded}: {self.score}"

    class Meta:
        ordering = ['-date_recorded', 'duration_choice']


class VolleyRecord(models.Model):
    """Record of consecutive volleys (forehand or backhand)."""
    class ShotType(models.TextChoices):
        FOREHAND = 'FH', 'Forehand'
        BACKHAND = 'BH', 'Backhand'

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='volley_records')
    date_recorded = models.DateField(default=timezone.now)
    shot_type = models.CharField(max_length=2, choices=ShotType.choices)
    consecutive_count = models.PositiveIntegerField()
    session = models.ForeignKey(
        Session, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='volley_tests_conducted',
        help_text="Optional: Link to the session where the test was done."
    )

    def __str__(self):
        return f"{self.get_shot_type_display()} Volley for {self.player} on {self.date_recorded}: {self.consecutive_count}"

    class Meta:
        ordering = ['-date_recorded', 'shot_type']


class BackwallDriveRecord(models.Model):
    """Record of consecutive backwall drives (forehand or backhand)."""
    class ShotType(models.TextChoices):
        FOREHAND = 'FH', 'Forehand'
        BACKHAND = 'BH', 'Backhand'

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='drive_records')
    date_recorded = models.DateField(default=timezone.now)
    shot_type = models.CharField(max_length=2, choices=ShotType.choices)
    consecutive_count = models.PositiveIntegerField()
    session = models.ForeignKey(
        Session, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='drive_tests_conducted',
        help_text="Optional: Link to the session where the test was done."
    )

    def __str__(self):
        return f"{self.get_shot_type_display()} Drive for {self.player} on {self.date_recorded}: {self.consecutive_count}"

    class Meta:
        ordering = ['-date_recorded', 'shot_type']

class MatchResult(models.Model):
    """Record of a practice or competitive match result."""
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='match_results')
    date = models.DateField(default=timezone.now)
    opponent_name = models.CharField(max_length=100, blank=True)
    player_score_str = models.CharField(max_length=50)
    opponent_score_str = models.CharField(max_length=50, blank=True)
    is_competitive = models.BooleanField(default=False, help_text="Was this an official league/tournament match?")
    match_notes = models.TextField(blank=True)
    session = models.ForeignKey(
        Session, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='matches_played',
        help_text="Optional: Link to the session if it was a practice match during training."
    )

    def __str__(self):
        match_type = "Competitive" if self.is_competitive else "Practice"
        return f"{match_type} Match for {self.player} on {self.date}"

    class Meta:
        ordering = ['-date', 'player__last_name']

# End of file
