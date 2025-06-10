# solosync_api/views.py
from rest_framework import viewsets, mixins, permissions
from django.db.models import Prefetch
# Import models used by the ViewSets
from .models import (
    SoloRoutine,
    SoloSessionLog,
    RoutineDrillLink,
    SoloDrill, # <-- Ensure SoloDrill is imported
    SoloSessionMetric,
    SoloDrillCategory # <-- Ensure SoloDrillCategory is imported
)
# Import serializers used by the ViewSets
from .serializers import (
    SoloRoutineSerializer,
    SoloSessionLogInputSerializer,
    SoloSessionLogOutputSerializer,
    SoloDrillSerializer # <-- Import the updated SoloDrillSerializer
)
import os
from django.http import FileResponse, Http404
from django.conf import settings

# Imports for filtering with django-filter
from django_filters import rest_framework as filters # Alias for clarity
from django_filters.filters import ModelMultipleChoiceFilter # For filtering by multiple categories

# --- FilterSet for SoloDrill ---
class SoloDrillFilter(filters.FilterSet):
    """
    FilterSet for SoloDrill model to allow filtering by categories,
    participant_type, and metric_type.
    """
    # Filter by categories (allows multiple category IDs, e.g., ?categories=1&categories=2)
    # This will filter drills that belong to ANY of the provided category IDs.
    categories = ModelMultipleChoiceFilter(
        field_name='categories__id', # Filter on the ID of the related SoloDrillCategory
        to_field_name='id',
        queryset=SoloDrillCategory.objects.all(),
        label='Filter by SoloDrillCategory IDs (e.g., ?categories=1&categories=2)'
    )
    # Alternative: Filter by category name (less precise if names aren't unique, but more readable)
    # categories__name = filters.CharFilter(field_name='categories__name', lookup_expr='iexact', label='Filter by category name (exact, case-insensitive)')


    class Meta:
        model = SoloDrill
        fields = {
            'participant_type': ['exact'], # e.g., ?participant_type=SOLO
            'metric_type': ['exact', 'isnull'], # e.g., ?metric_type=AMOUNT or ?metric_type__isnull=true
            # 'name': ['icontains'], # Optional: if you want to filter by name directly here
        }

# --- NEW ViewSet for SoloDrill ---
class SoloDrillViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows SoloDrills to be viewed.
    Supports filtering by category, participant_type, and metric_type.
    This is primarily for coaches/admins to fetch drills for routine building.
    """
    queryset = SoloDrill.objects.all().prefetch_related(
        'categories', # For efficient serialization of categories
        'created_by'
    ).order_by('name')
    serializer_class = SoloDrillSerializer
    permission_classes = [permissions.IsAuthenticated] # Or IsAdminUser if only admins/coaches build routines
    filter_backends = [filters.DjangoFilterBackend] # Enable DjangoFilterBackend
    filterset_class = SoloDrillFilter # Use the custom filterset

# --- Existing ViewSets ---

def serve_root_file(request, filename):
    path = os.path.join(settings.FRONTEND_BUILD_DIR, filename)
    if os.path.exists(path):
        return FileResponse(open(path, 'rb'))
    raise Http404()

class AssignedRoutinesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows assigned routines to be viewed by the logged-in player.
    Provides 'list' and 'retrieve' actions.
    """
    serializer_class = SoloRoutineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        prefetch_links = Prefetch(
            'routinedrilllink_set',
            queryset=RoutineDrillLink.objects.select_related('drill').order_by('order'),
        )
        # Corrected prefetch to use the prefetch_links object
        queryset = SoloRoutine.objects.filter(assigned_players=user).prefetch_related(
            prefetch_links # Use the defined Prefetch object
        ).distinct()
        return queryset


class SoloSessionLogViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return SoloSessionLogInputSerializer
        return SoloSessionLogOutputSerializer

    def get_queryset(self):
        """
        This method has been corrected to fix a 500 error.

        The original code used 'player__user' which is incorrect because the 'player'
        field on SoloSessionLog is a direct ForeignKey to the User model.

        The corrected code uses 'player' for filtering and 'player__username' for ordering.
        """
        user = self.request.user
        base_queryset = SoloSessionLog.objects.select_related(
            'player',  # Corrected from 'player__user'
            'routine'
        ).prefetch_related(
            Prefetch('solosessionmetric_set', queryset=SoloSessionMetric.objects.select_related('drill'))
        )
        
        if user.is_staff:
            # Coaches/staff can see all logs
            # Corrected the ordering to use 'player__username'
            queryset = base_queryset.all().order_by('-completed_at', 'player__username')
        else:
            # Players can only see their own logs
            # *** THIS IS THE MAIN FIX ***
            # Changed 'player__user=user' to 'player=user'
            queryset = base_queryset.filter(player=user).order_by('-completed_at')
            
        return queryset

    def perform_create(self, serializer):
        # This part correctly saves the logged-in user as the player.
        serializer.save(player=self.request.user)
