# solosync_api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction # Keep transaction import for create method

# Ensure all needed models are imported, including SoloDrillCategory
from .models import (
    SoloDrill,
    SoloRoutine,
    RoutineDrillLink,
    SoloSessionLog,
    SoloSessionMetric,
    SoloDrillCategory # <-- Make sure this is imported
)

UserModel = get_user_model()

# --- NEW Serializer for SoloDrillCategory ---
class SoloDrillCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for SoloDrillCategory model.
    """
    class Meta:
        model = SoloDrillCategory
        fields = ['id', 'name', 'description']

# --- UPDATED SoloDrillSerializer ---
class SoloDrillSerializer(serializers.ModelSerializer):
    """Serializer for SoloDrill information, including new categorization and metric type."""
    categories = SoloDrillCategorySerializer(many=True, read_only=True)
    participant_type_display = serializers.CharField(source='get_participant_type_display', read_only=True)
    metric_type_display = serializers.CharField(source='get_metric_type_display', read_only=True)

    # For write operations to set categories by ID
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=SoloDrillCategory.objects.all(),
        source='categories', # This maps to the 'categories' field on the model
        many=True,
        write_only=True,
        required=False # Categories are optional for a drill
    )

    class Meta:
        model = SoloDrill
        fields = [
            'id',
            'name',
            'description',
            'categories', # For reading category details
            'category_ids', # For writing category relationships
            'participant_type',
            'participant_type_display',
            'metric_type',
            'metric_type_display',
            'default_duration_seconds', # Added field
            'youtube_link',
            'created_by', # Consider making read_only if not set through API
            'created_at',
            'updated_at'
            # 'metrics_definition' field has been removed from the model
        ]
        read_only_fields = ('created_at', 'updated_at', 'created_by') # Example

# --- UPDATED RoutineDrillLinkSerializer ---
class RoutineDrillLinkSerializer(serializers.ModelSerializer):
    """Serializer for the link table, includes drill info & routine-specific settings"""
    drill_name = serializers.CharField(source='drill.name', read_only=True)
    youtube_link = serializers.URLField(source='drill.youtube_link', read_only=True, allow_null=True)
    # The metric type is now inherent to the drill itself (SoloDrill.metric_type)
    # So, we don't need to specify 'metrics_to_collect' here anymore.

    class Meta:
        model = RoutineDrillLink
        fields = [
            'order',
            'drill', # Drill ID
            'drill_name',
            'duration_seconds',
            'reps_target',
            'rest_after_seconds',
            # 'metrics_to_collect', # <-- REMOVED from fields as it's removed from the model
            'notes',
            'youtube_link',
        ]

# --- SoloRoutineSerializer (largely unchanged, but benefits from updated RoutineDrillLinkSerializer) ---
class SoloRoutineSerializer(serializers.ModelSerializer):
    """Serializer for SoloRoutine, includes steps, difficulty, duration"""
    routine_steps = RoutineDrillLinkSerializer(source='routinedrilllink_set', many=True, read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)
    difficulty_value = serializers.IntegerField(source='difficulty', read_only=True)
    total_duration_seconds = serializers.IntegerField(read_only=True)
    total_duration_display = serializers.CharField(read_only=True)

    class Meta:
        model = SoloRoutine
        fields = [
            'id',
            'name',
            'description',
            'created_by_username',
            'difficulty_display',
            'difficulty_value',
            'total_duration_seconds',
            'total_duration_display',
            'routine_steps',
        ]


# --- Serializers primarily for WRITING data (largely unchanged) ---

class SoloSessionMetricInputSerializer(serializers.Serializer):
    """Serializer for validating incoming metric data"""
    drill_id = serializers.PrimaryKeyRelatedField(queryset=SoloDrill.objects.all())
    metric_name = serializers.CharField(max_length=50, required=True) # This might need re-evaluation based on SoloDrill.metric_type
                                                                    # For now, keeping it as is. If SoloDrill.metric_type is 'AMOUNT',
                                                                    # metric_name could be 'count'. If 'TIME', it could be 'duration_recorded'.
    metric_value = serializers.CharField(max_length=100, required=True, allow_blank=False)


class SoloSessionLogInputSerializer(serializers.ModelSerializer):
    """Serializer used by the PWA to POST a completed session log"""
    player = serializers.PrimaryKeyRelatedField(read_only=True) # Should be set based on authenticated user in the view
    routine_id = serializers.PrimaryKeyRelatedField(queryset=SoloRoutine.objects.all(), source='routine', write_only=True)
    logged_metrics = SoloSessionMetricInputSerializer(many=True, write_only=True, required=False)
    completed_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = SoloSessionLog
        fields = [
            'id', 'player', 'routine_id', 'completed_at',
            'physical_difficulty', 'notes', 'logged_metrics',
        ]
        read_only_fields = ['id', 'player', 'completed_at']

    def create(self, validated_data):
        """Override create to handle nested metrics and set completed_at"""
        metrics_input_data = validated_data.pop('logged_metrics', [])
        validated_data['completed_at'] = timezone.now()
        # Ensure player is set from request.user in the view, not passed in validated_data directly by client
        # validated_data['player'] = self.context['request'].user # Example if player is not set before create

        session_log = None
        try:
            with transaction.atomic():
                session_log = SoloSessionLog.objects.create(**validated_data)
                for metric_data in metrics_input_data:
                    drill_instance = metric_data.get('drill_id')
                    metric_name = metric_data.get('metric_name')
                    metric_value = metric_data.get('metric_value')
                    if not drill_instance: continue
                    SoloSessionMetric.objects.create(
                        session_log=session_log, drill=drill_instance,
                        metric_name=metric_name, metric_value=metric_value
                    )
                return session_log
        except Exception as e:
            # It's good practice to log the actual exception e
            print(f"ERROR DURING SESSION LOG/METRIC CREATION: {e}")
            # import traceback
            # traceback.print_exc()
            raise e # Re-raise the exception so DRF can handle it and return an appropriate error response


# --- Serializers primarily for READING logged data (largely unchanged) ---

class SoloSessionMetricOutputSerializer(serializers.ModelSerializer):
    """Serializer for displaying individual logged metrics"""
    drill_name = serializers.CharField(source='drill.name', read_only=True)
    class Meta:
        model = SoloSessionMetric
        fields = ['drill_name', 'metric_name', 'metric_value']


class SoloSessionLogOutputSerializer(serializers.ModelSerializer):
    """Serializer for displaying details of a past session log"""
    routine_name = serializers.CharField(source='routine.name', read_only=True)
    player_username = serializers.CharField(source='player.username', read_only=True) # Assuming player model has a username field
    logged_metrics = SoloSessionMetricOutputSerializer(many=True, read_only=True, source='solosessionmetric_set') # Use related_name if default
    routine_difficulty_display = serializers.CharField(source='routine.get_difficulty_display', read_only=True, allow_null=True)

    class Meta:
        model = SoloSessionLog
        fields = [
            'id', 'player_username', 'routine_name', 'routine_difficulty_display',
            'completed_at', 'physical_difficulty', 'notes',
            'logged_metrics', 'created_at',
        ]

