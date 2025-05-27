# planning/models.py
import datetime
import io 
import re 
import os 

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, ExifTags 
from datetime import timedelta 
from django.conf import settings
User = settings.AUTH_USER_MODEL

# --- NEW MODEL: Venue ---
class Venue(models.Model):
    """Represents a physical venue where sessions can take place."""
    name = models.CharField(max_length=150, unique=True, help_text="Name of the venue (e.g., Midstream College Main Courts, Uitsig Court 1).")
    address = models.TextField(blank=True, null=True, help_text="Optional: Full address of the venue.")
    notes = models.TextField(blank=True, null=True, help_text="Optional: Any notes about the venue (e.g., access instructions, number of courts).")
    is_active = models.BooleanField(default=True, help_text="Is this venue currently in use?")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Venue"
        verbose_name_plural = "Venues"

# --- Supporting Models ---

class SchoolGroup(models.Model):
    """Represents a group of players, e.g., 'Boys U19 A'."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    attendance_form_url = models.URLField(
        max_length=1024, blank=True, null=True, verbose_name="Attendance Form URL",
        help_text="Link to the external Google Form or attendance sheet for this group."
    )
    def __str__(self): return self.name
    class Meta: ordering = ['name']


class Player(models.Model):
    """Represents a player."""
    class SkillLevel(models.TextChoices):
        BEGINNER = 'BEG', 'Beginner'; INTERMEDIATE = 'INT', 'Intermediate'; ADVANCED = 'ADV', 'Advanced'
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    date_of_birth = models.DateField(null=True, blank=True)
    skill_level = models.CharField(max_length=3, choices=SkillLevel.choices, default=SkillLevel.BEGINNER, blank=True)
    school_groups = models.ManyToManyField('SchoolGroup', related_name='players', blank=True)
    contact_number = models.CharField(max_length=20, blank=True, verbose_name="Player Contact Number", help_text="Enter number including country code if outside SA (e.g., +44... or 082...)")
    parent_contact_number = models.CharField(max_length=20, blank=True, verbose_name="Parent Contact Number", help_text="Enter number including country code if outside SA (e.g., +44... or 082...)")
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='player_photos/', null=True, blank=True)
    @property
    def full_name(self): return f"{self.first_name} {self.last_name}"
    def _format_for_whatsapp(self, number_str):
        if not number_str: return None
        cleaned_number = re.sub(r'[+\s\-\(\)]', '', number_str)
        if cleaned_number.startswith('0'): cleaned_number = '27' + cleaned_number[1:]
        if re.match(r'^\d{10,15}$', cleaned_number): return cleaned_number
        return None
    @property
    def whatsapp_number(self): return self._format_for_whatsapp(self.contact_number)
    @property
    def parent_whatsapp_number(self): return self._format_for_whatsapp(self.parent_contact_number)
    def __str__(self): return self.full_name
    def save(self, *args, **kwargs): # Image processing logic from before
        original_filename = None; process_image = False
        if self.pk:
            try:
                old_instance = Player.objects.get(pk=self.pk)
                if self.photo and old_instance.photo != self.photo:
                    process_image = True
                    if hasattr(self.photo, 'name') and self.photo.name: original_filename = self.photo.name
            except Player.DoesNotExist:
                process_image = True
                if self.photo and hasattr(self.photo, 'name') and self.photo.name: original_filename = self.photo.name
        elif self.photo:
            process_image = True
            if hasattr(self.photo, 'name') and self.photo.name: original_filename = self.photo.name
        super().save(*args, **kwargs) 
        if process_image and self.photo and hasattr(self.photo, 'path') and self.photo.path:
            try:
                filename_to_save = os.path.basename(original_filename if original_filename else self.photo.name)
                img = Image.open(self.photo.path); img = ImageOps.exif_transpose(img) 
                max_size = (300, 300); img.thumbnail(max_size, Image.Resampling.LANCZOS)
                img_format = img.format if img.format else 'JPEG'; buffer = io.BytesIO()
                save_kwargs = {'format': img_format, 'optimize': True}
                if img.mode in ("RGBA", "P") and img_format.upper() != 'PNG':
                    img = img.convert("RGB"); img_format = 'JPEG'
                    filename_to_save = os.path.splitext(filename_to_save)[0] + '.jpg'
                    save_kwargs['format'] = 'JPEG'
                if img_format.upper() == 'JPEG': save_kwargs['quality'] = 85
                img.save(buffer, **save_kwargs); resized_image = ContentFile(buffer.getvalue())
                current_photo_name = self.photo.name
                self.photo.save(filename_to_save, resized_image, save=False)
                if current_photo_name != self.photo.name: super().save(update_fields=['photo'])
            except FileNotFoundError: print(f"File not found for player photo {self.full_name}: {getattr(self.photo, 'path', 'No path')}")
            except Exception as e: print(f"Error processing player photo for {self.full_name}: {e}")
    class Meta: ordering = ['last_name', 'first_name']


class Coach(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coach_profile', null=True, blank=True )
    name = models.CharField(max_length=100, unique=True) 
    phone = models.CharField(max_length=20, blank=True); email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    hourly_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Coach's hourly rate for payment.")
    def __str__(self):
        if self.user and (self.user.get_full_name() or self.user.username): return self.user.get_full_name() or self.user.username
        return self.name 
    class Meta: ordering = ['name']; verbose_name_plural = "Coaches" 


class CoachFeedback(models.Model): 
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='feedback_entries')
    session = models.ForeignKey('Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_entries')
    date_recorded = models.DateTimeField(default=timezone.now) 
    strengths_observed = models.TextField(blank=True, verbose_name="Strengths Observed")
    areas_for_development = models.TextField(blank=True, verbose_name="Areas for Development")
    suggested_focus = models.TextField(blank=True, verbose_name="Suggested Focus/Next Steps")
    general_notes = models.TextField(blank=True, verbose_name="General Notes")
    class Meta: ordering = ['-date_recorded']; verbose_name = "Coach Feedback"; verbose_name_plural = "Coach Feedback Entries"
    def __str__(self):
        session_info = f" re: Session on {self.session.session_date.strftime('%Y-%m-%d')}" if self.session and self.session.session_date else ""
        return f"Feedback for {self.player.full_name} on {self.date_recorded.strftime('%Y-%m-%d')}{session_info}"


class Drill(models.Model):
    name = models.CharField(max_length=150, unique=True); description = models.TextField(blank=True)
    duration_minutes_default = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1)], help_text="Default duration in minutes...")
    PLAYER_COUNT_CHOICES = [(1, '1 Player'),(2, '2 Players'),(3, '3 Players'),(4, '4+ Players'),]
    ideal_num_players = models.IntegerField(choices=PLAYER_COUNT_CHOICES, null=True, blank=True, help_text="Ideal number of players...")
    suitable_for_any = models.BooleanField(default=False, help_text="Check if this drill works well regardless...")
    def __str__(self): return self.name
    class Meta: ordering = ['name']


class ScheduledClass(models.Model):
    DAY_OF_WEEK_CHOICES = [(0, 'Monday'),(1, 'Tuesday'),(2, 'Wednesday'),(3, 'Thursday'),(4, 'Friday'),(5, 'Saturday'),(6, 'Sunday')]
    school_group = models.ForeignKey(SchoolGroup, on_delete=models.CASCADE, related_name='scheduled_classes')
    day_of_week = models.IntegerField(choices=DAY_OF_WEEK_CHOICES)
    start_time = models.TimeField()
    default_duration_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)])
    # CHANGED: default_venue_name (CharField) to default_venue (ForeignKey)
    default_venue = models.ForeignKey(
        Venue, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Default venue for this recurring class."
    )
    default_coaches = models.ManyToManyField(Coach, blank=True, related_name='default_scheduled_classes')
    is_active = models.BooleanField(default=True, help_text="If unchecked, new sessions will not be generated from this rule.")
    notes_for_rule = models.TextField(blank=True, null=True, help_text="Internal notes about this recurring schedule rule.")
    def __str__(self):
        day_name = self.get_day_of_week_display()
        venue_name_str = f" at {self.default_venue.name}" if self.default_venue else ""
        return f"{self.school_group.name} - {day_name}s @ {self.start_time.strftime('%H:%M')}{venue_name_str}"
    class Meta:
        ordering = ['school_group__name', 'day_of_week', 'start_time']
        verbose_name = "Scheduled Class Rule"; verbose_name_plural = "Scheduled Class Rules"
        unique_together = ('school_group', 'day_of_week', 'start_time') 


class Session(models.Model):
    session_date = models.DateField(default=timezone.now); session_start_time = models.TimeField(default=timezone.now)
    planned_duration_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)])
    school_group = models.ForeignKey(SchoolGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    attendees = models.ManyToManyField(Player, related_name='attended_sessions', blank=True)
    coaches_attending = models.ManyToManyField(Coach, related_name='coached_sessions', blank=True)
    # CHANGED: venue_name (CharField) to venue (ForeignKey)
    venue = models.ForeignKey(
        Venue, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Venue where the session takes place."
    )
    is_cancelled = models.BooleanField(default=False, help_text="Mark as true if the session has been cancelled.")
    notes = models.TextField(blank=True, help_text="Optional objectives or notes for the session.")
    assessments_complete = models.BooleanField(default=False, help_text="Legacy field: Consider using CoachSessionCompletion instead.")
    generated_from_rule = models.ForeignKey(ScheduledClass, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_sessions', help_text="Link to the recurring schedule rule...")
    @property
    def start_datetime(self):
        if self.session_date and self.session_start_time:
            try: naive_dt = datetime.datetime.combine(self.session_date, self.session_start_time)
            except TypeError: return None
            if settings.USE_TZ:
                current_tz = timezone.get_current_timezone()
                try: return timezone.make_aware(naive_dt, current_tz)
                except Exception: return None
            else: return naive_dt
        return None
    @property
    def end_datetime(self):
        start_dt = self.start_datetime
        if start_dt and self.planned_duration_minutes is not None:
            try:
                duration = int(self.planned_duration_minutes)
                return start_dt + timedelta(minutes=duration)
            except (TypeError, ValueError): return None
        return None
    def __str__(self):
        group_name = self.school_group.name if self.school_group else "General"
        start_time_str = self.session_start_time.strftime('%H:%M') if self.session_start_time else '?:??'
        date_str = self.session_date.strftime('%Y-%m-%d') if self.session_date else '????-??-??'
        venue_str = f" at {self.venue.name}" if self.venue else ""
        return f"{group_name} Session on {date_str} at {start_time_str}{venue_str}"
    class Meta: ordering = ['-session_date', '-session_start_time']


class TimeBlock(models.Model):
    session = models.ForeignKey('Session', on_delete=models.CASCADE, related_name='time_blocks')
    start_offset_minutes = models.PositiveIntegerField(default=0, help_text="Minutes from session start time.")
    duration_minutes = models.PositiveIntegerField(default=15, validators=[MinValueValidator(1)])
    number_of_courts = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    rotation_interval_minutes = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)], help_text="Optional: Rotate players...")
    block_focus = models.CharField(max_length=200, blank=True, help_text="Specific focus for this time block...")
    @property
    def block_start_datetime(self):
        session_start_dt = self.session.start_datetime
        if session_start_dt:
            try: return session_start_dt + timedelta(minutes=int(self.start_offset_minutes))
            except (TypeError, ValueError): return None
        return None
    @property
    def block_end_datetime(self):
        start = self.block_start_datetime
        if start and self.duration_minutes:
            try: return start + timedelta(minutes=int(self.duration_minutes))
            except (TypeError, ValueError): return None
        return None
    def __str__(self):
        start_time_str = self.block_start_datetime.strftime('%H:%M') if self.block_start_datetime else '?:??'
        session_str = str(self.session) if self.session else "Unknown Session"
        return f"Block in {session_str} starting ~{start_time_str} ({self.duration_minutes} min)"
    class Meta: ordering = ['session', 'start_offset_minutes']


class ActivityAssignment(models.Model): 
    time_block = models.ForeignKey(TimeBlock, on_delete=models.CASCADE, related_name='activities')
    court_number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    drill = models.ForeignKey('Drill', on_delete=models.SET_NULL, null=True, blank=True)
    custom_activity_name = models.CharField(max_length=150, blank=True, help_text="Use this if not selecting a pre-defined Drill.")
    duration_minutes = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1)], help_text="Estimated duration...")
    lead_coach = models.ForeignKey('Coach', on_delete=models.SET_NULL, null=True, blank=True, related_name='led_activities')
    order = models.PositiveIntegerField(default=0, help_text="Order of activity...")
    activity_notes = models.TextField(blank=True, help_text="Specific notes...")
    def __str__(self):
        activity_name = self.drill.name if self.drill else self.custom_activity_name
        return f"{activity_name} on Court {self.court_number} in {self.time_block}"
    class Meta: ordering = ['time_block', 'court_number', 'order']


class ManualCourtAssignment(models.Model):
    time_block = models.ForeignKey(TimeBlock, on_delete=models.CASCADE, related_name='manual_assignments')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='manual_court_assignments')
    court_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    last_updated = models.DateTimeField(auto_now=True)
    def __str__(self): return f"{self.player} on Court {self.court_number} during {self.time_block}"
    class Meta: unique_together = ('time_block', 'player'); ordering = ['time_block', 'court_number', 'player__last_name']


class SessionAssessment(models.Model):
    class Rating(models.IntegerChoices): POOR = 1, 'Poor'; BELOW_AVERAGE = 2, 'Below Average'; AVERAGE = 3, 'Average'; GOOD = 4, 'Good'; EXCELLENT = 5, 'Excellent'
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='session_assessments')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='session_assessments_by_player') 
    date_recorded = models.DateField(default=timezone.now)
    effort_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True); focus_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    resilience_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True); composure_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    decision_making_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    coach_notes = models.TextField(blank=True)
    submitted_by = models.ForeignKey( User, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_assessments', limit_choices_to={'is_staff': True} )
    is_hidden = models.BooleanField(default=False, help_text="If true, this assessment is hidden...")
    superuser_reviewed = models.BooleanField(default=False, db_index=True, help_text="Checked by superuser if they have reviewed...")
    def __str__(self):
        submitter_name = self.submitted_by.username if self.submitted_by else "Unknown Coach"
        return f"Assessment for {self.player} in {self.session} by {submitter_name}"
    class Meta: unique_together = ('session', 'player', 'submitted_by'); ordering = ['-date_recorded', 'player__last_name']


class CourtSprintRecord(models.Model):
    class DurationChoice(models.TextChoices): THREE_MIN = '3m', '3 Minutes'; FIVE_MIN = '5m', '5 Minutes'; TEN_MIN = '10m', '10 Minutes'
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='sprint_records'); date_recorded = models.DateField(default=timezone.now)
    duration_choice = models.CharField(max_length=3, choices=DurationChoice.choices); score = models.PositiveIntegerField(help_text="Number of full court lengths completed.")
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='sprint_tests_conducted', help_text="Optional: Link to session...")
    def __str__(self): return f"Sprint ({self.get_duration_choice_display()}) for {self.player} on {self.date_recorded}: {self.score}"
    class Meta: ordering = ['-date_recorded', 'duration_choice']


class VolleyRecord(models.Model):
    class ShotType(models.TextChoices): FOREHAND = 'FH', 'Forehand'; BACKHAND = 'BH', 'Backhand'
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='volley_records'); date_recorded = models.DateField(default=timezone.now)
    shot_type = models.CharField(max_length=2, choices=ShotType.choices); consecutive_count = models.PositiveIntegerField()
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='volley_tests_conducted', help_text="Optional: Link to session...")
    def __str__(self): return f"{self.get_shot_type_display()} Volley for {self.player} on {self.date_recorded}: {self.consecutive_count}"
    class Meta: ordering = ['-date_recorded', 'shot_type']


class BackwallDriveRecord(models.Model):
    class ShotType(models.TextChoices): FOREHAND = 'FH', 'Forehand'; BACKHAND = 'BH', 'Backhand'
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='drive_records'); date_recorded = models.DateField(default=timezone.now)
    shot_type = models.CharField(max_length=2, choices=ShotType.choices); consecutive_count = models.PositiveIntegerField()
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='drive_tests_conducted', help_text="Optional: Link to session...")
    def __str__(self): return f"{self.get_shot_type_display()} Drive for {self.player} on {self.date_recorded}: {self.consecutive_count}"
    class Meta: ordering = ['-date_recorded', 'shot_type']


class MatchResult(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='match_results'); date = models.DateField(default=timezone.now)
    opponent_name = models.CharField(max_length=100, blank=True, null=True); player_score_str = models.CharField(max_length=50)
    opponent_score_str = models.CharField(max_length=50, blank=True, null=True)
    is_competitive = models.BooleanField(default=False, help_text="Was this an official league/tournament match?")
    match_notes = models.TextField(blank=True, null=True)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches_played', help_text="Optional: Link to session...")
    def __str__(self):
        match_type = "Competitive" if self.is_competitive else "Practice"
        return f"{match_type} Match for {self.player} on {self.date}"
    class Meta: ordering = ['-date', 'player__last_name']


class CoachAvailability(models.Model):
    coach = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='session_availabilities', limit_choices_to={'is_staff': True} )
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='coach_availabilities')
    is_available = models.BooleanField(default=True); notes = models.TextField(blank=True, help_text="Optional notes ...")
    timestamp = models.DateTimeField(auto_now=True, help_text="When this availability status was last saved.")
    ACTION_CHOICES = [('CONFIRM', 'Confirmed'), ('DECLINE', 'Declined')]
    last_action = models.CharField(max_length=10, choices=ACTION_CHOICES, null=True, blank=True, help_text="The last explicit action ...")
    status_updated_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of when ...")
    class Meta:
        unique_together = ('coach', 'session'); ordering = ['session__session_date', 'session__session_start_time', 'coach__username']
        verbose_name = "Coach Availability"; verbose_name_plural = "Coach Availabilities"
    def __str__(self):
        availability_status = "Available" if self.is_available else ("Unavailable" if self.is_available is False else "Pending")
        coach_name = self.coach.username if self.coach else "Unknown Coach"
        session_date_str = self.session.session_date.strftime('%Y-%m-%d') if self.session and self.session.session_date else "Unknown Date"
        return f"{coach_name} - {availability_status} for session on {session_date_str}"


class CoachSessionCompletion(models.Model):
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name='session_completions')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='coach_completions')
    assessments_submitted = models.BooleanField(default=False, help_text="True if the coach has submitted at least one assessment for this session.")
    confirmed_for_payment = models.BooleanField(default=False, help_text="Manually set by admin/superuser once duties are verified.")
    last_updated = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ('coach', 'session'); ordering = ['session__session_date', 'session__session_start_time', 'coach__name']
        verbose_name = "Coach Session Completion"; verbose_name_plural = "Coach Session Completions"
    def __str__(self):
        status = "Payment Confirmed" if self.confirmed_for_payment else ("Duties Complete" if self.assessments_submitted else "Pending Completion")
        coach_name = self.coach.name if self.coach else "Unknown Coach"
        session_date_str = self.session.session_date.strftime('%Y-%m-%d') if self.session and self.session.session_date else "Unknown Date"
        return f"{coach_name} - {status} for session on {session_date_str}"

class Payslip(models.Model):
    coach = models.ForeignKey(Coach, on_delete=models.PROTECT, related_name='payslips_generated_for')
    month = models.PositiveIntegerField(help_text="The month (1-12) of the payslip period.")
    year = models.PositiveIntegerField(help_text="The year (e.g., 2025) of the payslip period.")
    file = models.FileField(upload_to='payslips/%Y/%m/', help_text="The generated PDF payslip file.")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="The total amount payable on this payslip.")
    generated_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when this payslip record was created...")
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='payslips_initiated_by', help_text="The user who initiated...")
    class Meta:
        unique_together = ('coach', 'month', 'year'); ordering = ['-year', '-month', 'coach__user__last_name', 'coach__user__first_name', 'coach__name']
        verbose_name = "Payslip"; verbose_name_plural = "Payslips"
    def __str__(self):
        coach_display = str(self.coach) if self.coach else "Unknown Coach"
        return f"Payslip for {coach_display} - {self.month:02}/{self.year}"
    @property
    def filename(self):
        if self.file: return self.file.name.split('/')[-1]
        return None
