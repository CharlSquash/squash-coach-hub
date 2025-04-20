# planning/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
# Import the models needed for the forms
from .models import ( Player, SchoolGroup, Session, ActivityAssignment, Drill,
                      Coach, SessionAssessment, CourtSprintRecord,
                      VolleyRecord, BackwallDriveRecord, MatchResult ) # Added MatchResult

# --- Activity Assignment Form ---
class ActivityAssignmentForm(forms.ModelForm):
    class Meta:
        model = ActivityAssignment
        fields = ['drill', 'custom_activity_name', 'lead_coach', 'duration_minutes']
        labels = {
            'custom_activity_name': 'Custom Activity Name (if not selecting a drill)',
            'duration_minutes': 'Duration (minutes)',
            'lead_coach': 'Lead Coach (optional)',
            'drill': 'Select Drill (from library)',
        }
        help_texts = {
             'custom_activity_name': 'Enter a name only if you are not selecting a pre-defined Drill.',
             'drill': 'Select from the list only if you are not entering a Custom Activity Name.'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['drill'].required = False
        self.fields['lead_coach'].required = False

    def clean(self):
        cleaned_data = super().clean()
        drill = cleaned_data.get('drill')
        custom_name = cleaned_data.get('custom_activity_name')
        if drill and custom_name:
            self.add_error('drill', 'Please select a Drill OR enter a Custom Activity Name, not both.')
            self.add_error('custom_activity_name', 'Please select a Drill OR enter a Custom Activity Name, not both.')
        if not drill and not custom_name:
            self.add_error('drill', 'Please either select a Drill OR enter a Custom Activity Name.')
            self.add_error('custom_activity_name', 'Please either select a Drill OR enter a Custom Activity Name.')
        return cleaned_data


# --- Attendance Form ---
class AttendanceForm(forms.Form):
    attendees = forms.ModelMultipleChoiceField(
        queryset=Player.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Select Attendees from Group"
    )

    def __init__(self, *args, **kwargs):
        school_group = kwargs.pop('school_group', None)
        super().__init__(*args, **kwargs)

        if school_group:
            self.fields['attendees'].queryset = school_group.players.filter(
                is_active=True
            ).order_by('last_name', 'first_name')
        else:
            self.fields['attendees'].queryset = Player.objects.none()
            self.fields['attendees'].help_text = "No School Group assigned to this session. Assign a group to manage attendance."


# --- Session Assessment Form ---
class SessionAssessmentForm(forms.ModelForm):
    class Meta:
        model = SessionAssessment
        fields = ['effort_rating','focus_rating','resilience_rating','composure_rating','decision_making_rating','coach_notes']
        widgets = {
            'effort_rating': forms.RadioSelect, 'focus_rating': forms.RadioSelect,
            'resilience_rating': forms.RadioSelect, 'composure_rating': forms.RadioSelect,
            'decision_making_rating': forms.RadioSelect, 'coach_notes': forms.Textarea(attrs={'rows': 3})
        }
        labels = {
            'effort_rating': 'Effort / Motivation', 'focus_rating': 'Focus / Concentration',
            'resilience_rating': 'Resilience / Handling Pressure', 'composure_rating': 'Composure / Emotional Control',
            'decision_making_rating': 'Decision Making (Pressure)', 'coach_notes': 'Coach Notes (Optional)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            if field_name != 'coach_notes':
                self.fields[field_name].required = False


# --- Court Sprint Form ---
class CourtSprintRecordForm(forms.ModelForm):
    date_recorded = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=timezone.now().date()
    )

    class Meta:
        model = CourtSprintRecord
        fields = ['date_recorded', 'duration_choice', 'score', 'session']
        labels = {
            'date_recorded': 'Date Tested', 'duration_choice': 'Test Duration',
            'score': 'Amount of court sprints', 'session': 'Associated Session (Optional)'
        }
        help_texts = {
            'score': 'Enter the total number of full court lengths completed.'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['session'].required = False


# --- Volley Record Form ---
class VolleyRecordForm(forms.ModelForm):
    date_recorded = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.now().date())

    class Meta:
        model = VolleyRecord
        fields = ['date_recorded', 'shot_type', 'consecutive_count', 'session']
        labels = {
            'date_recorded': 'Date Tested', 'shot_type': 'Shot Type (FH/BH)',
            'consecutive_count': 'Consecutive Count', 'session': 'Associated Session (Optional)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['session'].required = False
        self.fields['shot_type'].widget = forms.RadioSelect()


# --- Backwall Drive Record Form ---
class BackwallDriveRecordForm(forms.ModelForm):
    date_recorded = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.now().date())

    class Meta:
        model = BackwallDriveRecord
        fields = ['date_recorded', 'shot_type', 'consecutive_count', 'session']
        labels = {
            'date_recorded': 'Date Tested', 'shot_type': 'Shot Type (FH/BH)',
            'consecutive_count': 'Consecutive Count', 'session': 'Associated Session (Optional)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['session'].required = False
        self.fields['shot_type'].widget = forms.RadioSelect()


# --- NEW Match Result Form ---
class MatchResultForm(forms.ModelForm):
    """Form for adding a match result."""
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.now().date())

    class Meta:
        model = MatchResult
        fields = [
            'date',
            'opponent_name',
            'player_score_str',
            'opponent_score_str',
            'is_competitive', # Should render as checkbox
            'match_notes',
            'session', # Optional link to session
        ]
        # Exclude 'player' - will be set in view
        labels = {
            'date': 'Match Date',
            'opponent_name': 'Opponent Name (Optional)',
            'player_score_str': 'Player Score / Result (e.g., 3-1 or 11-8, 11-5)',
            'opponent_score_str': 'Opponent Score / Result (Optional)',
            'is_competitive': 'Official Competitive Match?',
            'match_notes': 'Match Notes / Observations',
            'session': 'Associated Session (if practice match)',
        }
        widgets = {
            'match_notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['session'].required = False
        self.fields['opponent_name'].required = False
        self.fields['opponent_score_str'].required = False
        self.fields['match_notes'].required = False