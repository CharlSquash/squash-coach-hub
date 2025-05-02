# planning/models.py
# Added ManualCourtAssignment model
import datetime
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.files.base import ContentFile 
from PIL import Image
from PIL import Image, ImageOps 
import io
from datetime import timedelta  
from django.conf import settings
import re 


# Consider using settings.AUTH_USER_MODEL if you have a custom user model
User = settings.AUTH_USER_MODEL

# --- Supporting Models ---

class SchoolGroup(models.Model):
    """Represents a group of players, e.g., 'Boys U19 A'."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    attendance_form_url = models.URLField(
        max_length=1024, # Allow long URLs
        blank=True, 
        null=True,       # Make it optional
        verbose_name="Attendance Form URL",
        help_text="Link to the external Google Form or attendance sheet for this group."
    )

    

    def __str__(self):
        return self.name

# class SchoolGroup(models.Model): ... (if defined in the same file)

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
        'SchoolGroup', # Use quotes if SchoolGroup defined later/imported
        related_name='players',
        blank=True
    )
    contact_number = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name="Player Contact Number",
        help_text="Enter number including country code if outside SA (e.g., +44... or 082...)"
    )
    parent_contact_number = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name="Parent Contact Number",
        help_text="Enter number including country code if outside SA (e.g., +44... or 082...)"
    )

    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='player_photos/', null=True, blank=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name
    def _format_for_whatsapp(self, number_str):
        if not number_str:
            return None
        # Remove spaces, hyphens, parentheses, plus signs
        cleaned_number = re.sub(r'[+\s\-\(\)]', '', number_str)
        # Assume SA: If starts with 0, replace with 27
        if cleaned_number.startswith('0'):
            cleaned_number = '27' + cleaned_number[1:]
        # Basic check if it looks like an international number (already has country code)
        # You might need more robust validation depending on expected input formats
        if re.match(r'^\d{10,15}$', cleaned_number): # Simple digit check
             return cleaned_number
        return None # Return None if format seems invalid after cleaning

    @property
    def whatsapp_number(self):
        """ Returns the player's number formatted for wa.me links (SA focus). """
        return self._format_for_whatsapp(self.contact_number)

    @property
    def parent_whatsapp_number(self):
        """ Returns the parent's number formatted for wa.me links (SA focus). """
        return self._format_for_whatsapp(self.parent_contact_number)
    # --- END WHATSAPP PROPERTIES ---

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        # ... existing save method for image optimization ...
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['last_name', 'first_name']        

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # +++ ADD THIS SAVE METHOD FOR IMAGE OPTIMIZATION +++
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Inside class Player(models.Model):

    def save(self, *args, **kwargs):
        # Check if the photo field has a file associated with it
        if self.photo and hasattr(self.photo.file, 'read'):
            try:
                # Store the original filename
                filename = os.path.basename(self.photo.name) # Use basename

                # Open the image using Pillow directly from the field
                img = Image.open(self.photo)

                # --- FIX ORIENTATION ---
                img = ImageOps.exif_transpose(img) 
                # --- END FIX ---

                # Define maximum dimensions
                max_size = (300, 300)

                # Preserve aspect ratio while resizing down
                img.thumbnail(max_size, Image.Resampling.LANCZOS)

                # Prepare to save the resized image
                # Default to JPEG if format is lost after potential conversions
                img_format = img.format if img.format else 'JPEG' 
                buffer = io.BytesIO()
                save_kwargs = {'format': img_format, 'optimize': True}

                # Convert RGBA/P to RGB *before* saving if target format is not PNG
                # This prevents errors when saving formats like JPEG that don't support transparency
                if img.mode in ("RGBA", "P") and img_format.upper() != 'PNG':
                     img = img.convert("RGB")
                     img_format = 'JPEG' # Force JPEG format after conversion
                     filename = os.path.splitext(filename)[0] + '.jpg' # Update filename extension
                     save_kwargs['format'] = 'JPEG'

                # Set quality for JPEG
                if img_format.upper() == 'JPEG':
                    save_kwargs['quality'] = 85 # Adjust quality as needed

                # Save resized image to buffer
                img.save(buffer, **save_kwargs)

                # Create Django ContentFile
                resized_image = ContentFile(buffer.getvalue())

                # Save back to the ImageField without calling this save() method again
                self.photo.save(filename, resized_image, save=False)

            except Exception as e:
                print(f"Error processing player photo for {self.full_name}: {e}")
                # Decide how to handle error - e.g., clear photo or log more formally
                pass

        # Call the original model save method
        super().save(*args, **kwargs)

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

# Assuming a Coach model exists like this (or import it)
# class Coach(models.Model):
#     name = models.CharField(max_length=100)
#     # ... other fields ...
#     def __str__(self):
#         return self.name

class CoachFeedback(models.Model):
    """Stores structured feedback given by a coach to a player."""
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='feedback_entries')
    session = models.ForeignKey('Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_entries')
    # recorded_by = models.ForeignKey(Coach, on_delete=models.SET_NULL, null=True, blank=True) 
    # Or use settings.AUTH_USER_MODEL if using Django auth for coaches
    date_recorded = models.DateTimeField(auto_now_add=True)
    strengths_observed = models.TextField(blank=True, verbose_name="Strengths Observed")
    areas_for_development = models.TextField(blank=True, verbose_name="Areas for Development")
    suggested_focus = models.TextField(blank=True, verbose_name="Suggested Focus/Next Steps")
    general_notes = models.TextField(blank=True, verbose_name="General Notes")

    class Meta:
        ordering = ['-date_recorded'] # Show newest first
        verbose_name = "Coach Feedback"
        verbose_name_plural = "Coach Feedback Entries"

    def __str__(self):
        session_info = f" re: Session on {self.session.date}" if self.session else ""
        return f"Feedback for {self.player.full_name} on {self.date_recorded.strftime('%Y-%m-%d')}{session_info}"



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
    """Represents a training session."""

    # --- FIELD DEFINITIONS ---
    session_date = models.DateField(default=timezone.now) # Renamed to avoid conflict with datetime.date
    session_start_time = models.TimeField(default=timezone.now) # Renamed to avoid conflict
    planned_duration_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)])
    school_group = models.ForeignKey(
        'SchoolGroup', # Use quotes if SchoolGroup is defined later
        on_delete=models.SET_NULL, # Allow sessions without a group? Or use CASCADE?
        null=True,
        blank=True,
        related_name='sessions'
    )
    attendees = models.ManyToManyField(
        'Player', # Use quotes if Player is defined later
        related_name='attended_sessions',
        blank=True # Important for admin filter_horizontal/attendance form
    )
    coaches_attending = models.ManyToManyField(
        'Coach', # Use quotes if Coach is defined later
        related_name='coached_sessions',
        blank=True # Important for admin filter_horizontal
    )
    notes = models.TextField(blank=True, help_text="Optional objectives or notes for the session.")
    # --- ADD THIS FIELD ---
    assessments_complete = models.BooleanField(
        default=False,
        help_text="Mark as true once all player assessments for this session are done."
    )
    # --- END ADD THIS FIELD ---
    # --- END OF FIELD DEFINITIONS ---


    @property
    def start_datetime(self):
        """ Returns a timezone-aware datetime object for the session start. """
        # Uses the actual field names defined above
        if self.session_date and self.session_start_time:
            try:
                # This line requires the 'datetime' module to be imported
                naive_dt = datetime.datetime.combine(self.session_date, self.session_start_time)
            except TypeError as e:
                 print(f"Error combining date/time for Session {self.id}: {e}")
                 return None

            if settings.USE_TZ:
                current_tz = timezone.get_current_timezone()
                try:
                    return timezone.make_aware(naive_dt, current_tz)
                except Exception as e:
                    print(f"Error making datetime aware for Session {self.id}: {e}")
                    return None
            else:
                return naive_dt
        return None

    @property
    def end_datetime(self):
        """ Returns a timezone-aware datetime object for the session end. """
        start_dt = self.start_datetime
        if start_dt and self.planned_duration_minutes is not None:
            try:
                duration = int(self.planned_duration_minutes)
                # This line requires 'timedelta' from 'datetime' module (already imported)
                return start_dt + timedelta(minutes=duration)
            except (TypeError, ValueError) as e:
                print(f"Error calculating end_datetime for Session {self.id}: Invalid duration '{self.planned_duration_minutes}'. Error: {e}")
                return None
        return None


    def __str__(self):
        # Uses the actual field names
        group_name = self.school_group.name if self.school_group else "General"
        start_time_str = self.session_start_time.strftime('%H:%M') if self.session_start_time else '?:??'
        date_str = self.session_date.strftime('%Y-%m-%d') if self.session_date else '????-??-??'
        return f"{group_name} Session on {date_str} at {start_time_str}"

    class Meta:
        # Uses the actual field names defined above
        ordering = ['-session_date', '-session_start_time']

    class Meta:
        # Uses the actual field names defined above
        ordering = ['-session_date', '-session_start_time']


class TimeBlock(models.Model):
    """Represents a segment of time within a Session."""
    session = models.ForeignKey('Session', on_delete=models.CASCADE, related_name='time_blocks') # Use quotes if Session is defined later
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
        # Use the Session's start_datetime property (which should now be correct)
        session_start_dt = self.session.start_datetime
        if session_start_dt:
            try:
                # Add the offset to the session's aware start datetime
                return session_start_dt + timedelta(minutes=int(self.start_offset_minutes))
            except (TypeError, ValueError):
                return None
        # Fallback if session start time isn't available (less ideal)
        elif self.session.date and self.session.start_time:
             # Combine date and time into a naive datetime
             # CORRECTED LINE: Use datetime.datetime.combine
             naive_dt = datetime.datetime.combine(self.session.date, self.session.start_time)
             if settings.USE_TZ:
                 current_tz = timezone.get_current_timezone()
                 aware_dt = timezone.make_aware(naive_dt, current_tz)
             else:
                 aware_dt = naive_dt # Treat as naive if USE_TZ is False

             try:
                 # Add offset to this calculated start time
                 return aware_dt + timedelta(minutes=int(self.start_offset_minutes))
             except (TypeError, ValueError):
                 return None
        return None


    @property
    def block_end_datetime(self):
        """Calculate the absolute end datetime of the block."""
        start = self.block_start_datetime # Uses the corrected block_start_datetime
        if start and self.duration_minutes:
            try:
                return start + timedelta(minutes=int(self.duration_minutes))
            except (TypeError, ValueError):
                return None
        return None

    def __str__(self):
        start_time_str = self.block_start_datetime.strftime('%H:%M') if self.block_start_datetime else '?:??'
        # Use session's __str__ representation if available
        session_str = str(self.session) if self.session else "Unknown Session"
        return f"Block in {session_str} starting ~{start_time_str} ({self.duration_minutes} min)"

    class Meta:
        ordering = ['session', 'start_offset_minutes']

# Make sure Coach and Drill models are defined or imported if used below
# from .models import Coach, Drill

class ActivityAssignment(models.Model):
    """Assigns a Drill or custom activity to a court within a TimeBlock."""
    time_block = models.ForeignKey(TimeBlock, on_delete=models.CASCADE, related_name='activities')
    court_number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    drill = models.ForeignKey('Drill', on_delete=models.SET_NULL, null=True, blank=True) # Use quotes if Drill defined later
    custom_activity_name = models.CharField(
        max_length=150, blank=True,
        help_text="Use this if not selecting a pre-defined Drill."
    )
    duration_minutes = models.PositiveIntegerField(
        default=10, validators=[MinValueValidator(1)],
        help_text="Estimated duration for this specific activity."
    )
    lead_coach = models.ForeignKey(
        'Coach', on_delete=models.SET_NULL, null=True, blank=True, # Use quotes if Coach defined later
        related_name='led_activities'
    )
    order = models.PositiveIntegerField(default=0, help_text="Order of activity within the court/block (0 first).")
    activity_notes = models.TextField(blank=True, help_text="Specific notes for this activity instance.")

    def __str__(self):
        activity_name = self.drill.name if self.drill else self.custom_activity_name
        # Use time_block's __str__ representation
        time_block_str = str(self.time_block) if self.time_block else "Unknown TimeBlock"
        return f"{activity_name} on Court {self.court_number} in {time_block_str}"

    class Meta:
        ordering = ['time_block', 'court_number', 'order']


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
