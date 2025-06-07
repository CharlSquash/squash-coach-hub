# planning/models.py
import datetime # Keep this as it's used in Session model properties
import io
import re
import os

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.files.base import ContentFile
from PIL import Image, ImageOps
from datetime import timedelta
from django.conf import settings
User = settings.AUTH_USER_MODEL

# --- MODEL: Venue ---
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

# --- MODEL: SchoolGroup ---
class SchoolGroup(models.Model):
    """Represents a group of players, e.g., 'Boys U19 A'."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    attendance_form_url = models.URLField(
        max_length=1024, blank=True, null=True, verbose_name="Attendance Form URL",
        help_text="Link to the external Google Form or attendance sheet for this group."
    )
    def __str__(self):
        return self.name
    class Meta:
        ordering = ['name']


# --- MODEL: Coach ---
class Coach(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coach_profile', null=True, blank=True )
    name = models.CharField(max_length=100, unique=True) # Ensure this is not redundant if user.get_full_name() is primary
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    hourly_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Coach's hourly rate for payment.")
    
    whatsapp_phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="WhatsApp enabled phone number in E.164 format (e.g., +14155238886)."
    )
    whatsapp_opt_in = models.BooleanField(
        default=False,
        help_text="Has the coach opted-in to receive WhatsApp notifications?"
    )
    receive_weekly_schedule_email = models.BooleanField(
        default=True,
        verbose_name="Receive Weekly Schedule Email",
        help_text="If checked, this coach will receive the weekly schedule summary email every Sunday."
    )

    # +++ NEW FIELDS for Coach Profile +++
    profile_photo = models.ImageField(
        upload_to='coach_photos/', 
        null=True, 
        blank=True,
        verbose_name="Profile Photo"
    )
    experience_notes = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Coaching Experience",
        help_text="Brief notes on coaching experience, specializations, etc."
    )

    class QualificationLevel(models.TextChoices):
        NONE = 'NONE', 'None / Not Applicable'
        LEVEL_1 = 'L1', 'Level 1'
        LEVEL_2 = 'L2', 'Level 2'
        LEVEL_3 = 'L3', 'Level 3'
        OTHER = 'OTH', 'Other'
        # Add more levels if needed

    qualification_wsf_level = models.CharField(
        max_length=5,
        choices=QualificationLevel.choices,
        default=QualificationLevel.NONE,
        blank=True,
        verbose_name="WSF Qualification Level",
        help_text="World Squash Federation coaching qualification level."
    )
    qualification_ssa_level = models.CharField(
        max_length=5,
        choices=QualificationLevel.choices, # Assuming same levels apply, or create separate choices
        default=QualificationLevel.NONE,
        blank=True,
        verbose_name="SSA Qualification Level",
        help_text="Squash South Africa coaching qualification level."
    )
    # +++ END NEW FIELDS +++

    def __str__(self):
        if self.user and (self.user.get_full_name() or self.user.username):
            return self.user.get_full_name() or self.user.username
        return self.name 
    
    def save(self, *args, **kwargs):
        # --- Photo optimization logic (similar to Player model) ---
        original_filename = None
        process_image = False

        if self.pk: 
            try:
                old_instance = Coach.objects.get(pk=self.pk)
                if self.profile_photo and old_instance.profile_photo != self.profile_photo: 
                    process_image = True
                    if hasattr(self.profile_photo, 'name') and self.profile_photo.name:
                        original_filename = self.profile_photo.name
                elif not self.profile_photo and old_instance.profile_photo: 
                    pass # Photo removed
            except Coach.DoesNotExist:
                if self.profile_photo: 
                    process_image = True
                    if hasattr(self.profile_photo, 'name') and self.profile_photo.name:
                        original_filename = self.profile_photo.name
        elif self.profile_photo: 
            process_image = True
            if hasattr(self.profile_photo, 'name') and self.profile_photo.name:
                original_filename = self.profile_photo.name
        
        super().save(*args, **kwargs) # Save first

        if process_image and self.profile_photo and hasattr(self.profile_photo, 'path') and self.profile_photo.path:
            try:
                filename_to_save = os.path.basename(original_filename if original_filename else self.profile_photo.name)
                img = Image.open(self.profile_photo.path)
                img = ImageOps.exif_transpose(img)

                max_size = (300, 300) # Consistent with player photo size
                img.thumbnail(max_size, Image.Resampling.LANCZOS)

                img_format = img.format if img.format else 'JPEG'
                buffer = io.BytesIO()
                save_kwargs = {'format': img_format, 'optimize': True}

                if img.mode in ("RGBA", "P") and img_format.upper() != 'PNG':
                    img = img.convert("RGB")
                    img_format = 'JPEG'
                    filename_to_save = os.path.splitext(filename_to_save)[0] + '.jpg'
                    save_kwargs['format'] = 'JPEG'
                
                if img_format.upper() == 'JPEG':
                    save_kwargs['quality'] = 85

                img.save(buffer, **save_kwargs)
                resized_image = ContentFile(buffer.getvalue())
                
                current_photo_name = self.profile_photo.name
                self.profile_photo.save(filename_to_save, resized_image, save=False) 
                
                if current_photo_name != self.profile_photo.name or kwargs.get('force_insert', False):
                    super().save(update_fields=['profile_photo'])
            except FileNotFoundError:
                print(f"File not found for coach photo {self.name}: {getattr(self.profile_photo, 'path', 'No path')}")
            except Exception as e:
                print(f"Error processing coach photo for {self.name}: {e}")
        # --- End photo optimization ---

    class Meta:
        ordering = ['name'] 
        verbose_name_plural = "Coaches"


# --- MODEL: Player ---
class Player(models.Model):
    """Represents a player."""
    class SkillLevel(models.TextChoices):
        BEGINNER = 'BEG', 'Beginner'
        INTERMEDIATE = 'INT', 'Intermediate'
        ADVANCED = 'ADV', 'Advanced'

    class GradeLevel(models.IntegerChoices):
        GRADE_R = 0, 'Grade R'
        GRADE_1 = 1, 'Grade 1'
        GRADE_2 = 2, 'Grade 2'
        GRADE_3 = 3, 'Grade 3'
        GRADE_4 = 4, 'Grade 4'
        GRADE_5 = 5, 'Grade 5'
        GRADE_6 = 6, 'Grade 6'
        GRADE_7 = 7, 'Grade 7'
        GRADE_8 = 8, 'Grade 8'
        GRADE_9 = 9, 'Grade 9'
        GRADE_10 = 10, 'Grade 10'
        GRADE_11 = 11, 'Grade 11'
        GRADE_12 = 12, 'Grade 12 (Matric)'
        OTHER = 99, 'Other / Not Applicable'

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    grade = models.IntegerField(
        choices=GradeLevel.choices,
        null=True,
        blank=True,
        verbose_name="School Grade"
    )
    skill_level = models.CharField(
        max_length=3,
        choices=SkillLevel.choices,
        default=SkillLevel.BEGINNER,
        blank=True
    )
    school_groups = models.ManyToManyField('SchoolGroup', related_name='players', blank=True)
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
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='player_photos/', null=True, blank=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def _format_for_whatsapp(self, number_str):
        if not number_str:
            return None
        cleaned_number = re.sub(r'[+\s\-\(\)]', '', number_str)
        if cleaned_number.startswith('0'):
            cleaned_number = '27' + cleaned_number[1:]
        if re.match(r'^\d{10,15}$', cleaned_number): # Basic E.164-like check (without specific country length validation)
            return cleaned_number
        return None # Or raise ValidationError for invalid format

    @property
    def whatsapp_number(self):
        return self._format_for_whatsapp(self.contact_number)

    @property
    def parent_whatsapp_number(self):
        return self._format_for_whatsapp(self.parent_contact_number)

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        original_filename = None
        process_image = False

        if self.pk: # Check if instance already exists
            try:
                old_instance = Player.objects.get(pk=self.pk)
                if self.photo and old_instance.photo != self.photo: # Photo changed
                    process_image = True
                    if hasattr(self.photo, 'name') and self.photo.name:
                        original_filename = self.photo.name
                elif not self.photo and old_instance.photo: # Photo removed
                    # Potentially delete old_instance.photo.delete(save=False) if desired
                    pass
            except Player.DoesNotExist: # Should not happen if self.pk exists but good for safety
                if self.photo: # New instance being saved with a photo for the first time (e.g. after form error)
                    process_image = True
                    if hasattr(self.photo, 'name') and self.photo.name:
                        original_filename = self.photo.name
        elif self.photo: # New instance, photo provided
            process_image = True
            if hasattr(self.photo, 'name') and self.photo.name:
                original_filename = self.photo.name
        
        super().save(*args, **kwargs) # Save first to ensure file path if it's a new upload

        if process_image and self.photo and hasattr(self.photo, 'path') and self.photo.path:
            try:
                # Use original_filename if available (especially if self.photo.name gets modified by storage)
                filename_to_save = os.path.basename(original_filename if original_filename else self.photo.name)

                img = Image.open(self.photo.path)
                img = ImageOps.exif_transpose(img) # Corrects orientation based on EXIF

                max_size = (300, 300) # Define your max thumbnail size
                img.thumbnail(max_size, Image.Resampling.LANCZOS)

                img_format = img.format if img.format else 'JPEG' # Default to JPEG if format is not detectable
                buffer = io.BytesIO()
                save_kwargs = {'format': img_format, 'optimize': True}

                # Ensure RGB for JPEG, handle transparency for PNG
                if img.mode in ("RGBA", "P") and img_format.upper() != 'PNG':
                    img = img.convert("RGB")
                    img_format = 'JPEG' # Output format becomes JPEG
                    filename_to_save = os.path.splitext(filename_to_save)[0] + '.jpg'
                    save_kwargs['format'] = 'JPEG'
                
                if img_format.upper() == 'JPEG':
                    save_kwargs['quality'] = 85 # Adjust quality as needed

                img.save(buffer, **save_kwargs)
                resized_image = ContentFile(buffer.getvalue())

                # Store the current name before saving the new file content
                current_photo_name = self.photo.name
                
                # Save the resized image content to the same field path, with potentially new filename
                self.photo.save(filename_to_save, resized_image, save=False) 
                
                # If the file name changed OR if this was a new instance (force_insert)
                # we need to call super().save() again to update the photo field in DB.
                if current_photo_name != self.photo.name or kwargs.get('force_insert', False):
                    super().save(update_fields=['photo'])

            except FileNotFoundError:
                # This might happen if self.photo.path is incorrect or file removed externally
                print(f"File not found for player photo {self.full_name}: {getattr(self.photo, 'path', 'No path')}")
            except Exception as e:
                print(f"Error processing player photo for {self.full_name}: {e}")

    class Meta:
        ordering = ['last_name', 'first_name']

# --- MODEL: Drill ---
class Drill(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    duration_minutes_default = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1)], help_text="Default duration in minutes for this drill.")
    PLAYER_COUNT_CHOICES = [
        (1, '1 Player'),
        (2, '2 Players'),
        (3, '3 Players'),
        (4, '4+ Players'),
    ]
    ideal_num_players = models.IntegerField(choices=PLAYER_COUNT_CHOICES, null=True, blank=True, help_text="Ideal number of players for this drill.")
    suitable_for_any = models.BooleanField(default=False, help_text="Check if this drill works well regardless of specific group skill level or size (within reason).")

    youtube_link = models.URLField(
        max_length=1024, 
        blank=True, 
        null=True, 
        verbose_name="YouTube Link",
        help_text="Optional: A link to a YouTube video demonstrating the drill."
    )

    def __str__(self):
        return self.name
    class Meta:
        ordering = ['name']


# --- MODEL: ScheduledClass ---
class ScheduledClass(models.Model):
    DAY_OF_WEEK_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
        (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ]
    school_group = models.ForeignKey('SchoolGroup', on_delete=models.CASCADE, related_name='scheduled_classes')
    day_of_week = models.IntegerField(choices=DAY_OF_WEEK_CHOICES)
    start_time = models.TimeField()
    default_duration_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)])
    default_venue = models.ForeignKey('Venue', on_delete=models.SET_NULL, null=True, blank=True, help_text="Default venue for this recurring class.")
    default_coaches = models.ManyToManyField('Coach', blank=True, related_name='default_scheduled_classes')
    is_active = models.BooleanField(default=True, help_text="If unchecked, new sessions will not be generated from this rule.")
    notes_for_rule = models.TextField(blank=True, null=True, help_text="Internal notes about this recurring schedule rule.")

    def __str__(self):
        day_name = self.get_day_of_week_display()
        venue_name_str = f" at {self.default_venue.name}" if self.default_venue else ""
        return f"{self.school_group.name} - {day_name}s @ {self.start_time.strftime('%H:%M')}{venue_name_str}"
    class Meta:
        ordering = ['school_group__name', 'day_of_week', 'start_time']
        verbose_name = "Scheduled Class Rule"
        verbose_name_plural = "Scheduled Class Rules"
        unique_together = ('school_group', 'day_of_week', 'start_time')


# --- MODEL: Session ---
class Session(models.Model):
    session_date = models.DateField(default=timezone.now)
    session_start_time = models.TimeField(default=timezone.now)
    planned_duration_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)])
    school_group = models.ForeignKey('SchoolGroup', on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    attendees = models.ManyToManyField('Player', related_name='attended_sessions', blank=True)
    coaches_attending = models.ManyToManyField('Coach', related_name='coached_sessions', blank=True)
    venue = models.ForeignKey('Venue', on_delete=models.SET_NULL, null=True, blank=True, help_text="Venue where the session takes place.")
    is_cancelled = models.BooleanField(default=False, help_text="Mark as true if the session has been cancelled.")
    notes = models.TextField(blank=True, help_text="Optional objectives or notes for the session.")
    assessments_complete = models.BooleanField(default=False, help_text="Legacy field: Consider using CoachSessionCompletion instead or a property to check if all expected assessments are in.")
    generated_from_rule = models.ForeignKey('ScheduledClass', on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_sessions', help_text="Link to the recurring schedule rule, if this session was auto-generated.")
    
    @property
    def start_datetime(self):
        if self.session_date and self.session_start_time:
            try:
                naive_dt = datetime.datetime.combine(self.session_date, self.session_start_time)
            except TypeError: # e.g. if session_start_time is None, though field doesn't allow it
                return None
            if settings.USE_TZ:
                current_tz = timezone.get_current_timezone()
                try:
                    return timezone.make_aware(naive_dt, current_tz)
                except Exception: # Catch specific errors like AmbiguousTimeError, NonExistentTimeError if needed
                    return None # Or handle more gracefully
            else:
                return naive_dt
        return None
        
    @property
    def end_datetime(self):
        start_dt = self.start_datetime
        if start_dt and self.planned_duration_minutes is not None:
            try:
                duration = int(self.planned_duration_minutes)
                return start_dt + timedelta(minutes=duration)
            except (TypeError, ValueError): # Should not happen if planned_duration_minutes is PositiveIntegerField
                return None
        return None
        
    def __str__(self):
        group_name = self.school_group.name if self.school_group else "General"
        start_time_str = self.session_start_time.strftime('%H:%M') if self.session_start_time else '?:??'
        date_str = self.session_date.strftime('%Y-%m-%d') if self.session_date else '????-??-??'
        venue_str = f" at {self.venue.name}" if self.venue else ""
        return f"{group_name} Session on {date_str} at {start_time_str}{venue_str}"
    class Meta:
        ordering = ['-session_date', '-session_start_time']


# --- MODEL: TimeBlock ---
class TimeBlock(models.Model):
    session = models.ForeignKey('Session', on_delete=models.CASCADE, related_name='time_blocks')
    start_offset_minutes = models.PositiveIntegerField(default=0, help_text="Minutes from session start time.")
    duration_minutes = models.PositiveIntegerField(default=15, validators=[MinValueValidator(1)])
    number_of_courts = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    rotation_interval_minutes = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)], help_text="Optional: Rotate players/activities every X minutes within this block.")
    block_focus = models.CharField(max_length=200, blank=True, help_text="Specific focus for this time block (e.g., Warm-up, Drills, Match Play).")
    
    @property
    def block_start_datetime(self):
        session_start_dt = self.session.start_datetime
        if session_start_dt:
            try:
                return session_start_dt + timedelta(minutes=int(self.start_offset_minutes))
            except (TypeError, ValueError): return None
        return None
        
    @property
    def block_end_datetime(self):
        start = self.block_start_datetime
        if start and self.duration_minutes:
            try:
                return start + timedelta(minutes=int(self.duration_minutes))
            except (TypeError, ValueError): return None
        return None
        
    def __str__(self):
        start_time_str = self.block_start_datetime.strftime('%H:%M') if self.block_start_datetime else '?:??'
        session_str = str(self.session) if self.session else "Unknown Session"
        focus_str = f" - {self.block_focus}" if self.block_focus else ""
        return f"Block in {session_str} starting ~{start_time_str} ({self.duration_minutes} min){focus_str}"
    class Meta:
        ordering = ['session', 'start_offset_minutes']

# --- MODEL: ActivityAssignment ---
class ActivityAssignment(models.Model): 
    time_block = models.ForeignKey('TimeBlock', on_delete=models.CASCADE, related_name='activities')
    court_number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    drill = models.ForeignKey('Drill', on_delete=models.SET_NULL, null=True, blank=True)
    custom_activity_name = models.CharField(max_length=150, blank=True, help_text="Use this if not selecting a pre-defined Drill.")
    duration_minutes = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1)], help_text="Estimated duration for this activity on this court.")
    lead_coach = models.ForeignKey('Coach', on_delete=models.SET_NULL, null=True, blank=True, related_name='led_activities')
    order = models.PositiveIntegerField(default=0, help_text="Order of activity on this court within the time block.")
    activity_notes = models.TextField(blank=True, help_text="Specific notes for this activity instance (e.g., variations, player assignments).")

    def __str__(self):
        activity_name = self.drill.name if self.drill else self.custom_activity_name
        return f"{activity_name} on Court {self.court_number} in {self.time_block}"
    class Meta:
        ordering = ['time_block', 'court_number', 'order']

# --- MODEL: CoachFeedback (General Player Feedback, not session specific) ---
class CoachFeedback(models.Model): 
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='feedback_entries')
    session = models.ForeignKey('Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_entries') # Can be general or linked to a session
    date_recorded = models.DateTimeField(default=timezone.now) 
    strengths_observed = models.TextField(blank=True, verbose_name="Strengths Observed")
    areas_for_development = models.TextField(blank=True, verbose_name="Areas for Development")
    suggested_focus = models.TextField(blank=True, verbose_name="Suggested Focus/Next Steps")
    general_notes = models.TextField(blank=True, verbose_name="General Notes")

    class Meta: 
        ordering = ['-date_recorded', 'player__last_name']
        verbose_name = "Coach Feedback"
        verbose_name_plural = "Coach Feedback Entries"

    def __str__(self):
        session_info = f" re: Session on {self.session.session_date.strftime('%Y-%m-%d')}" if self.session and self.session.session_date else ""
        return f"Feedback for {self.player.full_name} on {self.date_recorded.strftime('%Y-%m-%d %H:%M')}{session_info}"


# --- MODEL: ManualCourtAssignment (If specific players are manually placed on courts within a time block) ---
class ManualCourtAssignment(models.Model):
    time_block = models.ForeignKey('TimeBlock', on_delete=models.CASCADE, related_name='manual_assignments')
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='manual_court_assignments')
    court_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.player} on Court {self.court_number} during {self.time_block}"
    class Meta: 
        unique_together = ('time_block', 'player') # A player can only be assigned to one court in a time_block
        ordering = ['time_block', 'court_number', 'player__last_name']


# --- MODEL: SessionAssessment (Individual Player Assessment for a Session) ---
class SessionAssessment(models.Model):
    class Rating(models.IntegerChoices): 
        POOR = 1, 'Poor'
        BELOW_AVERAGE = 2, 'Below Average'
        AVERAGE = 3, 'Average'
        GOOD = 4, 'Good'
        EXCELLENT = 5, 'Excellent'

    session = models.ForeignKey('Session', on_delete=models.CASCADE, related_name='session_assessments')
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='session_assessments_by_player') 
    date_recorded = models.DateField(default=timezone.now) # Or DateTimeField if time is important
    effort_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    focus_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    resilience_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    composure_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    decision_making_rating = models.IntegerField(choices=Rating.choices, null=True, blank=True)
    coach_notes = models.TextField(blank=True)
    submitted_by = models.ForeignKey( 
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='submitted_player_assessments', # Changed related_name to be specific
        limit_choices_to={'is_staff': True} 
    )
    is_hidden = models.BooleanField(default=False, help_text="If true, this assessment is hidden from player/parent view (admin/coach only).")
    superuser_reviewed = models.BooleanField(default=False, db_index=True, help_text="Checked by superuser if they have reviewed this assessment.")

    def __str__(self):
        submitter_name = self.submitted_by.username if self.submitted_by else "Unknown Coach"
        return f"Assessment for {self.player} in {self.session} by {submitter_name}"
    class Meta: 
        unique_together = ('session', 'player', 'submitted_by') # Assuming one coach submits one assessment per player per session
        ordering = ['-date_recorded', 'player__last_name']

# --- NEW MODEL: GroupAssessment ---
class GroupAssessment(models.Model):
    session = models.ForeignKey('Session', on_delete=models.CASCADE, related_name='group_assessments')
    # SchoolGroup can be accessed via self.session.school_group if that link is reliable and singular.
    # If you need to explicitly link to a SchoolGroup (e.g., if a session could be for multiple, or no group)
    # then uncomment the line below and adjust logic. For now, assuming session.school_group is sufficient.
    # school_group = models.ForeignKey('SchoolGroup', on_delete=models.CASCADE, related_name='group_assessments_direct', null=True, blank=True)
    
    assessing_coach = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, # Or False if assessing_coach should always be set
        related_name='submitted_group_assessments',
        limit_choices_to={'is_staff': True},
        help_text="Coach (User account) who submitted this assessment."
    )
    assessment_datetime = models.DateTimeField(default=timezone.now, help_text="When the assessment was submitted.")
    general_notes = models.TextField(blank=True, help_text="Coach's general assessment notes for the group/session (e.g., group commitment, venue issues, parent interactions).")
    is_hidden_from_other_coaches = models.BooleanField(
        default=False, 
        help_text="If true, this assessment is hidden from other coaches (visible only to assessing coach and superusers)."
    )
    superuser_reviewed = models.BooleanField(
        default=False,
        db_index=True, # Good for filtering performance
        help_text="Checked by superuser if they have reviewed this group assessment."
    )

    def __str__(self):
        coach_name = self.assessing_coach.username if self.assessing_coach else "Unknown Coach"
        # Access school_group name via session for the string representation
        group_name = self.session.school_group.name if self.session and self.session.school_group else "N/A Group"
        session_date_str = self.session.session_date.strftime('%Y-%m-%d') if self.session and self.session.session_date else "Unknown Date"
        
        return f"Group Assessment for {group_name} (Session: {session_date_str}) by {coach_name}"

    class Meta:
        ordering = ['-assessment_datetime', 'session']
        # A coach can only assess a specific session once for group feedback.
        # If multiple coaches can assess the same session, this unique_together might be too restrictive
        # or should include 'assessing_coach'.
        unique_together = ('session', 'assessing_coach') 
        verbose_name = "Group Assessment"
        verbose_name_plural = "Group Assessments"


# --- MODEL: CourtSprintRecord ---
class CourtSprintRecord(models.Model):
    class DurationChoice(models.TextChoices): 
        THREE_MIN = '3m', '3 Minutes'
        FIVE_MIN = '5m', '5 Minutes'
        TEN_MIN = '10m', '10 Minutes'
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='sprint_records')
    date_recorded = models.DateField(default=timezone.now)
    duration_choice = models.CharField(max_length=3, choices=DurationChoice.choices)
    score = models.PositiveIntegerField(help_text="Number of full court lengths completed.")
    session = models.ForeignKey('Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='sprint_tests_conducted', help_text="Optional: Link to session where this test was conducted.")
    def __str__(self):
        return f"Sprint ({self.get_duration_choice_display()}) for {self.player} on {self.date_recorded}: {self.score}"
    class Meta:
        ordering = ['-date_recorded', 'duration_choice']


# --- MODEL: VolleyRecord ---
class VolleyRecord(models.Model):
    class ShotType(models.TextChoices): 
        FOREHAND = 'FH', 'Forehand'
        BACKHAND = 'BH', 'Backhand'
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='volley_records')
    date_recorded = models.DateField(default=timezone.now)
    shot_type = models.CharField(max_length=2, choices=ShotType.choices)
    consecutive_count = models.PositiveIntegerField()
    session = models.ForeignKey('Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='volley_tests_conducted', help_text="Optional: Link to session where this test was conducted.")
    def __str__(self):
        return f"{self.get_shot_type_display()} Volley for {self.player} on {self.date_recorded}: {self.consecutive_count}"
    class Meta:
        ordering = ['-date_recorded', 'shot_type']


# --- MODEL: BackwallDriveRecord ---
class BackwallDriveRecord(models.Model):
    class ShotType(models.TextChoices): 
        FOREHAND = 'FH', 'Forehand'
        BACKHAND = 'BH', 'Backhand'
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='drive_records')
    date_recorded = models.DateField(default=timezone.now)
    shot_type = models.CharField(max_length=2, choices=ShotType.choices)
    consecutive_count = models.PositiveIntegerField()
    session = models.ForeignKey('Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='drive_tests_conducted', help_text="Optional: Link to session where this test was conducted.")
    def __str__(self):
        return f"{self.get_shot_type_display()} Drive for {self.player} on {self.date_recorded}: {self.consecutive_count}"
    class Meta:
        ordering = ['-date_recorded', 'shot_type']


# --- MODEL: MatchResult ---
class MatchResult(models.Model):
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='match_results')
    date = models.DateField(default=timezone.now)
    opponent_name = models.CharField(max_length=100, blank=True, null=True)
    player_score_str = models.CharField(max_length=50, help_text="Player's score, e.g., '3-1' or '11-9, 11-5, 11-7'")
    opponent_score_str = models.CharField(max_length=50, blank=True, null=True, help_text="Opponent's score if different from player's perspective")
    is_competitive = models.BooleanField(default=False, help_text="Was this an official league/tournament match?")
    match_notes = models.TextField(blank=True, null=True)
    session = models.ForeignKey('Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='matches_played', help_text="Optional: Link to session if this match was part of it.")
    def __str__(self):
        match_type = "Competitive" if self.is_competitive else "Practice"
        return f"{match_type} Match for {self.player} on {self.date}"
    class Meta:
        ordering = ['-date', 'player__last_name']


# --- MODEL: CoachAvailability ---
class CoachAvailability(models.Model):
    coach = models.ForeignKey( 
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='session_availabilities', 
        limit_choices_to={'is_staff': True} 
    )
    session = models.ForeignKey('Session', on_delete=models.CASCADE, related_name='coach_availabilities')
    is_available = models.BooleanField(default=True, null=True) # Allowing Null to mean "Pending response"
    notes = models.TextField(blank=True, help_text="Optional notes (e.g., reason for unavailability).")
    timestamp = models.DateTimeField(auto_now=True, help_text="When this availability status was last saved.")
    ACTION_CHOICES = [('CONFIRM', 'Confirmed'), ('DECLINE', 'Declined')]
    last_action = models.CharField(max_length=10, choices=ACTION_CHOICES, null=True, blank=True, help_text="The last explicit action taken by the coach via confirmation link.")
    status_updated_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of when the status was explicitly confirmed or declined.")

    class Meta:
        unique_together = ('coach', 'session')
        ordering = ['session__session_date', 'session__session_start_time', 'coach__username']
        verbose_name = "Coach Availability"
        verbose_name_plural = "Coach Availabilities"

    def __str__(self):
        if self.is_available is True:
            availability_status = "Available"
        elif self.is_available is False:
            availability_status = "Unavailable"
        else:
            availability_status = "Pending" # if is_available is Null
            
        coach_name = self.coach.username if self.coach else "Unknown Coach"
        session_date_str = self.session.session_date.strftime('%Y-%m-%d') if self.session and self.session.session_date else "Unknown Date"
        return f"{coach_name} - {availability_status} for session on {session_date_str}"

# --- MODEL: CoachSessionCompletion ---
class CoachSessionCompletion(models.Model):
    coach = models.ForeignKey('Coach', on_delete=models.CASCADE, related_name='session_completions')
    session = models.ForeignKey('Session', on_delete=models.CASCADE, related_name='coach_completions')
    assessments_submitted = models.BooleanField(default=False, help_text="True if the coach has submitted all required player assessments for this session for their assigned players.")
    # group_assessment_submitted = models.BooleanField(default=False, help_text="True if the coach has submitted the group assessment for this session.") # Consider adding this
    confirmed_for_payment = models.BooleanField(default=False, help_text="Manually set by admin/superuser once duties are verified and all assessments are complete.")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('coach', 'session')
        ordering = ['session__session_date', 'session__session_start_time', 'coach__name']
        verbose_name = "Coach Session Completion"
        verbose_name_plural = "Coach Session Completions"

    def __str__(self):
        status = "Payment Confirmed" if self.confirmed_for_payment else ("Duties Complete" if self.assessments_submitted else "Pending Completion") # Add group_assessment_submitted here if used
        coach_name = self.coach.name if self.coach else "Unknown Coach"
        session_date_str = self.session.session_date.strftime('%Y-%m-%d') if self.session and self.session.session_date else "Unknown Date"
        return f"{coach_name} - {status} for session on {session_date_str}"

# --- MODEL: Payslip ---
class Payslip(models.Model):
    coach = models.ForeignKey('Coach', on_delete=models.PROTECT, related_name='payslips_generated_for')
    month = models.PositiveIntegerField(help_text="The month (1-12) of the payslip period.")
    year = models.PositiveIntegerField(help_text="The year (e.g., 2025) of the payslip period.")
    file = models.FileField(upload_to='payslips/%Y/%m/', help_text="The generated PDF payslip file.")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="The total amount payable on this payslip.")
    generated_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when this payslip record was created in the system.")
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='payslips_initiated_by', 
        help_text="The user who initiated the generation of this payslip."
    )
    class Meta:
        unique_together = ('coach', 'month', 'year')
        ordering = ['-year', '-month', 'coach__name'] # Updated ordering
        verbose_name = "Payslip"
        verbose_name_plural = "Payslips"

    def __str__(self):
        coach_display = str(self.coach) if self.coach else "Unknown Coach"
        return f"Payslip for {coach_display} - {self.month:02}/{self.year}"

    @property
    def filename(self):
        if self.file:
            return os.path.basename(self.file.name)
        return None


# planning/models.py
# ... (your existing imports and other model definitions like Venue, SchoolGroup, Coach, Player, Session etc.)

# +++ NEW MODEL: Event +++
class Event(models.Model):
    class EventType(models.TextChoices):
        SOCIAL = 'SOCIAL', 'Social Event'
        TOURNAMENT = 'TOURNMT', 'Tournament Support' # Abbreviated for potential length constraints if any
        SCHOOL = 'SCHOOL', 'School Function'
        CEREMONY = 'CEREMONY', 'Capping/Awards Ceremony'
        MEETING = 'MEETING', 'Coach/Staff Meeting'
        WORKSHOP = 'WORKSHOP', 'Workshop/Training'
        OTHER = 'OTHER', 'Other Event'

    name = models.CharField(
        max_length=200,
        help_text="Name of the event (e.g., Midstream Social Saturday - June, St. Alban's Tournament U19)."
    )
    event_type = models.CharField(
        max_length=10, # Max length of the choice keys (e.g., 'TOURNMT')
        choices=EventType.choices,
        default=EventType.OTHER,
        verbose_name="Event Type"
    )
    event_date = models.DateTimeField( # Using DateTimeField to allow for specific start times if needed
        default=timezone.now, # Or just models.DateField() if time is not important
        verbose_name="Event Date & Time"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional: Further details about the event."
    )
    attending_coaches = models.ManyToManyField(
        'Coach',
        related_name='attended_events',
        blank=True, # A coach might be added later, or no coaches might be relevant for some event types initially
        verbose_name="Attending Coaches"
    )
    # Optional: Add a venue if events are typically at a specific place
    # venue = models.ForeignKey('Venue', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.get_event_type_display()}) on {self.event_date.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-event_date', 'name']
        verbose_name = "Event"
        verbose_name_plural = "Events"
# +++ END NEW MODEL: Event +++


# ... (rest of your models.py file, including GroupAssessment if already added) ...