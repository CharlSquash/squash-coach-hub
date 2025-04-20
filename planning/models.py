# planning/models.py
from django.db import models
from django.utils import timezone
from django.utils.timezone import make_aware
import datetime

# --- Choices ---
DRILL_CATEGORY_CHOICES = [ # ... (as before) ...
    ('TECH', 'Technique'), ('FOOT', 'Footwork'), ('COND', 'Condition Game'),
    ('FIT', 'Fitness'), ('TACT', 'Tactics'), ('MENT', 'Mental Skill'),
    ('SERV', 'Serve/Return'), ('OTHR', 'Other'),
]

# --- Models ---

# === Session Planning Models ===

class Drill(models.Model):
    name = models.CharField(max_length=200, help_text="The name of the drill.")
    description = models.TextField(help_text="Detailed description...")
    category = models.CharField(max_length=4, choices=DRILL_CATEGORY_CHOICES, help_text="Primary category.")
    duration_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Suggested duration (optional).")
    def __str__(self): return self.name
    # Add Meta class
    class Meta:
        verbose_name_plural = "Session Planning | Drills"

class Coach(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name
    # Add Meta class
    class Meta:
        verbose_name_plural = "Session Planning | Coaches"


class Session(models.Model):
    # Add school_group ForeignKey FIRST if not already moved before Player/Coach
    school_group = models.ForeignKey('SchoolGroup', on_delete=models.SET_NULL, null=True, blank=False, related_name='sessions', help_text="The group this session is for.")
    date = models.DateField(default=timezone.now); start_time = models.TimeField()
    planned_duration_minutes = models.PositiveIntegerField(default=90, help_text="Total planned duration.")
    notes = models.TextField(blank=True, help_text="Overall notes/objectives.")
    coaches_attending = models.ManyToManyField('Coach', blank=True, related_name='sessions_attending') # Use strings if Coach defined later
    attendees = models.ManyToManyField('Player', blank=True, related_name='sessions_attended', help_text="Players marked as attending.") # Use strings if Player defined later
    class Meta:
        ordering = ['-date', '-start_time']
        verbose_name_plural = "Session Planning | Sessions" # Add verbose name

    def __str__(self):
        group_name = self.school_group.name if self.school_group else "Ungrouped Session"
        return f"{group_name} on {self.date.strftime('%Y-%m-%d')} at {self.start_time.strftime('%H:%M')}"

class TimeBlock(models.Model):
    session = models.ForeignKey(Session, related_name='time_blocks', on_delete=models.CASCADE)
    start_offset_minutes = models.PositiveIntegerField(default=0, help_text="Start offset from session start.")
    duration_minutes = models.PositiveIntegerField(help_text="Duration of this block.")
    number_of_courts = models.PositiveIntegerField(default=1, help_text="Courts available.")
    rotation_interval_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Rotate groups every X minutes. Leave blank/0 for no rotation.")
    block_focus = models.CharField(max_length=255, blank=True, help_text="Optional focus.")
    @property
    def block_start_datetime(self): # ... as before ...
         if self.session.date and self.session.start_time:
             try: naive_session_start_dt = datetime.datetime.combine(self.session.date, self.session.start_time); aware_session_start_dt = make_aware(naive_session_start_dt); return aware_session_start_dt + datetime.timedelta(minutes=self.start_offset_minutes)
             except TypeError: return None
         return None
    @property
    def block_end_datetime(self): # ... as before ...
         start_dt = self.block_start_datetime
         if start_dt and self.duration_minutes is not None:
             try: return start_dt + datetime.timedelta(minutes=self.duration_minutes)
             except TypeError: return None
         return None
    class Meta:
        ordering = ['session', 'start_offset_minutes']
        # No verbose name needed if not shown directly in admin index

    def __str__(self): # ... as before ...
         start_time_str = self.block_start_datetime.strftime('%H:%M') if self.block_start_datetime else f"Offset {self.start_offset_minutes}m"; session_group_str = self.session.school_group.name if self.session.school_group else 'Session'; return f"{session_group_str} {self.session.date} - Block @ {start_time_str}"

class ActivityAssignment(models.Model):
    time_block = models.ForeignKey(TimeBlock, related_name='activities', on_delete=models.CASCADE)
    court_number = models.PositiveIntegerField(help_text="Which court (e.g., 1, 2).")
    drill = models.ForeignKey(Drill, null=True, blank=True, on_delete=models.SET_NULL)
    custom_activity_name = models.CharField(max_length=200, blank=True, help_text="Use if not selecting a Drill.")
    lead_coach = models.ForeignKey(Coach, null=True, blank=True, on_delete=models.SET_NULL)
    duration_minutes = models.PositiveIntegerField(help_text="Duration for this activity.")
    order = models.PositiveIntegerField(default=0, help_text="Order on court within block.")
    class Meta:
        ordering = ['time_block', 'court_number', 'order']
        verbose_name_plural = "Session Planning | Activity Assignments" # Add verbose name

    def __str__(self): # ... as before ...
        activity_name = self.drill.name if self.drill else self.custom_activity_name; session_str = f"{self.time_block.session.date}@{self.time_block.session.start_time.strftime('%H:%M')}"; block_start_str = self.time_block.block_start_datetime.strftime('%H:%M') if self.time_block.block_start_datetime else f"{self.time_block.start_offset_minutes}m"; return f"S:{session_str} B:@{block_start_str} C:{self.court_number} - {activity_name} ({self.duration_minutes}m)"

# === Player Related Models ===

class Player(models.Model):
    class SkillLevel(models.TextChoices): # ... as before ...
         BEGINNER = 'BEG', 'Beginner'; INTERMEDIATE = 'INT', 'Intermediate'; ADVANCED = 'ADV', 'Advanced'
    first_name = models.CharField(max_length=100); last_name = models.CharField(max_length=100)
    skill_level = models.CharField(max_length=3, choices=SkillLevel.choices, default=SkillLevel.INTERMEDIATE, help_text="Approximate skill level.")
    is_active = models.BooleanField(default=True, help_text="Uncheck if player is no longer active.")
    photo = models.ImageField(upload_to='player_photos/', null=True, blank=True, help_text="Optional profile photo.")
    class Meta:
         ordering = ['last_name', 'first_name']
         verbose_name_plural = "Player Profiles | Players" # Add verbose name
    def __str__(self): return f"{self.first_name} {self.last_name}"
    @property
    def full_name(self): return f"{self.first_name} {self.last_name}"

class SchoolGroup(models.Model):
    name = models.CharField(max_length=150, unique=True, help_text="Name of the school group")
    description = models.TextField(blank=True, help_text="Optional description.")
    players = models.ManyToManyField(Player, blank=True, related_name='school_groups')
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Player Profiles | School Groups" # Add verbose name
    def __str__(self): return self.name

class SessionAssessment(models.Model):
    class Rating(models.IntegerChoices): ONE = 1, '1 Star'; TWO = 2, '2 Stars'; THREE = 3, '3 Stars'; FOUR = 4, '4 Stars'; FIVE = 5, '5 Stars'
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='session_assessments')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='player_assessments')
    date_recorded = models.DateField(default=timezone.now)
    effort_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True, help_text="Effort/motivation rating (1-5).")
    focus_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True, help_text="Focus rating (1-5).")
    resilience_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True, help_text="Resilience rating (1-5).")
    composure_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True, help_text="Composure rating (1-5).")
    decision_making_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True, help_text="Decision making rating (1-5).")
    coach_notes = models.TextField(blank=True, help_text="Specific observations.")
    class Meta:
        ordering = ['-date_recorded', 'player']
        unique_together = ['player', 'session']
        verbose_name_plural = "Player Records | Session Assessments" # Add verbose name
    def __str__(self): return f"Assessment for {self.player} on {self.session.date}"

class CourtSprintRecord(models.Model):
    class Duration(models.TextChoices): THREE_MIN = '3m', '3 Minutes'; FIVE_MIN = '5m', '5 Minutes'; TEN_MIN = '10m', '10 Minutes'
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='sprint_records')
    date_recorded = models.DateField(default=timezone.now)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='sprint_tests')
    duration_choice = models.CharField(max_length=3, choices=Duration.choices, help_text="Duration of the sprint test.")
    score = models.IntegerField(help_text="Score achieved (e.g., number of laps completed).")
    class Meta:
        ordering = ['player', '-date_recorded', 'duration_choice']
        verbose_name_plural = "Player Records | Court Sprints" # Add verbose name
    def __str__(self): return f"Sprint ({self.duration_choice}): {self.score} for {self.player} on {self.date_recorded}"

class VolleyRecord(models.Model):
    class ShotType(models.TextChoices): FH = 'FH', 'Forehand'; BH = 'BH', 'Backhand'
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='volley_records')
    date_recorded = models.DateField(default=timezone.now)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='volley_tests')
    shot_type = models.CharField(max_length=2, choices=ShotType.choices)
    consecutive_count = models.PositiveIntegerField(help_text="Number of consecutive volleys hit successfully.")
    class Meta:
        ordering = ['player', '-date_recorded', 'shot_type']
        verbose_name_plural = "Player Records | Volleys" # Add verbose name
    def __str__(self): return f"Volley ({self.shot_type}): {self.consecutive_count} for {self.player} on {self.date_recorded}"

class BackwallDriveRecord(models.Model):
    class ShotType(models.TextChoices): FH = 'FH', 'Forehand'; BH = 'BH', 'Backhand'
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='drive_records')
    date_recorded = models.DateField(default=timezone.now)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='drive_tests')
    shot_type = models.CharField(max_length=2, choices=ShotType.choices)
    consecutive_count = models.PositiveIntegerField(help_text="Number of consecutive drives off the back wall.")
    class Meta:
        ordering = ['player', '-date_recorded', 'shot_type']
        verbose_name_plural = "Player Records | Backwall Drives" # Add verbose name
    def __str__(self): return f"Backwall Drive ({self.shot_type}): {self.consecutive_count} for {self.player} on {self.date_recorded}"

class MatchResult(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='match_results')
    date = models.DateField(default=timezone.now)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='practice_matches', help_text="Link if practice match.")
    opponent_name = models.CharField(max_length=200, blank=True)
    player_score_str = models.CharField(max_length=100, help_text="Score details (e.g., 3-1, or 11-8, 11-9...)")
    opponent_score_str = models.CharField(max_length=100, blank=True)
    is_competitive = models.BooleanField(default=False, help_text="Check if official competitive match.")
    match_notes = models.TextField(blank=True, help_text="Coach observations, etc.")
    class Meta:
        ordering = ['player', '-date']
        verbose_name_plural = "Player Records | Match Results" # Add verbose name
    def __str__(self): # ... as before ...
        match_type = "Competitive" if self.is_competitive else "Practice"; vs = f"vs {self.opponent_name}" if self.opponent_name else ""; return f"{match_type} Match for {self.player} on {self.date} {vs}"