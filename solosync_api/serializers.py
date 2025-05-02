# solosync_api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction # Keep transaction import for create method
# Ensure all needed models are imported
from .models import SoloDrill, SoloRoutine, RoutineDrillLink, SoloSessionLog, SoloSessionMetric

UserModel = get_user_model()

# --- Serializers primarily for READING data ---

class SoloDrillSerializer(serializers.ModelSerializer):
    """Serializer for basic SoloDrill information (now includes youtube_link)"""
    class Meta:
        model = SoloDrill
        # Add youtube_link to the fields list
        fields = ['id', 'name', 'description', 'metrics_definition', 'youtube_link'] # Added youtube_link


class RoutineDrillLinkSerializer(serializers.ModelSerializer):
    """Serializer for the link table, includes drill info & routine-specific settings"""
    drill_name = serializers.CharField(source='drill.name', read_only=True)
    # *** ADDED: youtube_link sourced from the related drill ***
    youtube_link = serializers.URLField(source='drill.youtube_link', read_only=True, allow_null=True)

    class Meta:
        model = RoutineDrillLink
        # *** UPDATED: Added youtube_link to the fields list ***
        fields = [
            'order',
            'drill', # Drill ID
            'drill_name',
            'duration_seconds',
            'reps_target',
            'rest_after_seconds',
            'metrics_to_collect',
            'notes',
            'youtube_link', # <-- Field added here
        ]


class SoloRoutineSerializer(serializers.ModelSerializer):
    """Serializer for SoloRoutine, includes steps, difficulty, duration"""
    # Use the explicit related_name='routinedrilllink_set' from the model FK
    routine_steps = RoutineDrillLinkSerializer(source='routinedrilllink_set', many=True, read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    # Use model properties/methods for difficulty/duration
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)
    difficulty_value = serializers.IntegerField(source='difficulty', read_only=True)
    total_duration_seconds = serializers.IntegerField(read_only=True) # From @property
    total_duration_display = serializers.CharField(read_only=True) # From model method

    class Meta:
        model = SoloRoutine
        # Fields list includes new difficulty/duration fields
        fields = [
            'id',
            'name',
            'description',
            'created_by_username',
            'difficulty_display',
            'difficulty_value',
            'total_duration_seconds',
            'total_duration_display',
            'routine_steps', # Includes nested steps with youtube_link now
        ]


# --- Serializers primarily for WRITING data ---

class SoloSessionMetricInputSerializer(serializers.Serializer):
    """Serializer for validating incoming metric data"""
    drill_id = serializers.PrimaryKeyRelatedField(queryset=SoloDrill.objects.all())
    metric_name = serializers.CharField(max_length=50, required=True)
    metric_value = serializers.CharField(max_length=100, required=True, allow_blank=False)


class SoloSessionLogInputSerializer(serializers.ModelSerializer):
    """Serializer used by the PWA to POST a completed session log"""
    player = serializers.PrimaryKeyRelatedField(read_only=True)
    routine_id = serializers.PrimaryKeyRelatedField(queryset=SoloRoutine.objects.all(), source='routine', write_only=True)
    logged_metrics = SoloSessionMetricInputSerializer(many=True, write_only=True, required=False)
    completed_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = SoloSessionLog
        # Use corrected field names matching model
        fields = [
            'id', 'player', 'routine_id', 'completed_at',
            'physical_difficulty', 'notes', 'logged_metrics',
        ]
        read_only_fields = ['id', 'player', 'completed_at']

    def create(self, validated_data):
        """Override create to handle nested metrics and set completed_at"""
        metrics_input_data = validated_data.pop('logged_metrics', [])
        validated_data['completed_at'] = timezone.now()
        session_log = None
        try:
            with transaction.atomic():
                # print("--- Starting Session Log Creation ---") # Keep debug prints removed
                # print(f"Validated Log Data (before create): {validated_data}")
                session_log = SoloSessionLog.objects.create(**validated_data)
                # print(f"SUCCESS: Created SoloSessionLog with ID: {session_log.id}")
                # print(f"Attempting to create {len(metrics_input_data)} metrics...")
                for metric_data in metrics_input_data:
                    # print(f"  Processing metric data: {metric_data}")
                    drill_instance = metric_data.get('drill_id')
                    metric_name = metric_data.get('metric_name')
                    metric_value = metric_data.get('metric_value')
                    if not drill_instance: continue
                    SoloSessionMetric.objects.create(
                        session_log=session_log, drill=drill_instance,
                        metric_name=metric_name, metric_value=metric_value
                    )
                    # print(f"  SUCCESS: Created SoloSessionMetric...")
            # print(f"--- Successfully committed transaction for Session Log ID: {session_log.id} ---")
            return session_log
        except Exception as e:
             print(f"--- ERROR DURING SESSION LOG/METRIC CREATION ---")
             print(f"Exception Type: {type(e).__name__}")
             print(f"Exception Args: {e.args}")
             import traceback
             traceback.print_exc()
             raise e


# --- Serializers primarily for READING logged data ---

class SoloSessionMetricOutputSerializer(serializers.ModelSerializer):
    """Serializer for displaying individual logged metrics"""
    drill_name = serializers.CharField(source='drill.name', read_only=True)
    class Meta:
        model = SoloSessionMetric
        fields = ['drill_name', 'metric_name', 'metric_value']


class SoloSessionLogOutputSerializer(serializers.ModelSerializer):
    """Serializer for displaying details of a past session log"""
    routine_name = serializers.CharField(source='routine.name', read_only=True)
    player_username = serializers.CharField(source='player.username', read_only=True)
    logged_metrics = SoloSessionMetricOutputSerializer(many=True, read_only=True)
    routine_difficulty_display = serializers.CharField(source='routine.get_difficulty_display', read_only=True, allow_null=True)

    class Meta:
        model = SoloSessionLog
        # Use corrected field names from model
        fields = [
            'id', 'player_username', 'routine_name', 'routine_difficulty_display',
            'completed_at', 'physical_difficulty', 'notes',
            'logged_metrics', 'created_at',
        ]