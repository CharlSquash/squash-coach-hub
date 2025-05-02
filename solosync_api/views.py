# solosync_api/views.py
from rest_framework import viewsets, mixins, permissions
from django.db.models import Prefetch
from .models import SoloRoutine, SoloSessionLog, RoutineDrillLink, SoloDrill, SoloSessionMetric
from .serializers import (
    SoloRoutineSerializer,
    SoloSessionLogInputSerializer,
    SoloSessionLogOutputSerializer
)


# --- ViewSet for fetching routines assigned to the logged-in player ---
class AssignedRoutinesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows assigned routines to be viewed by the logged-in player.
    Provides 'list' and 'retrieve' actions.
    """
    serializer_class = SoloRoutineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        This view should return a list of all the routines
        assigned to the currently authenticated user.
        """
        user = self.request.user
        prefetch_links = Prefetch(
            'routinedrilllink_set',
            queryset=RoutineDrillLink.objects.select_related('drill').order_by('order'),
        )
        queryset = SoloRoutine.objects.filter(assigned_players=user).prefetch_related(
             'routinedrilllink_set'
        ).distinct()
        return queryset


# --- ViewSet for creating AND viewing completed sessions ---
class SoloSessionLogViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    API endpoint for Solo Session Logs.
    Allows:
     - Creating (POST) a new session log (player).
     - Listing (GET) logs (filtered by role: coach sees all, player sees own).
     - Retrieving (GET) a specific log (filtered by role).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """ Return appropriate serializer class based on action """
        if self.action == 'create':
            return SoloSessionLogInputSerializer
        return SoloSessionLogOutputSerializer

    # *** MODIFIED get_queryset method for Coach/Player access ***
    def get_queryset(self):
        """
        Filter logs:
        - If user is staff (coach assumption), return all logs.
        - Otherwise (player), return only their own logs.
        """
        user = self.request.user
        print(f"User {user.username} (is_staff={user.is_staff}) fetching session logs.") # Debug print

        # Define base queryset with optimizations usable for both cases
        base_queryset = SoloSessionLog.objects.select_related(
            'player', # Needed for display
            'routine'
        ).prefetch_related(
            Prefetch('logged_metrics', queryset=SoloSessionMetric.objects.select_related('drill'))
        )

        # Check if the user is considered a coach (using is_staff for now)
        # TODO: Replace user.is_staff with a more robust role check if needed (e.g., groups)
        if user.is_staff:
            print(f"User {user.username} is staff, returning all logs.")
            # Staff/Coach sees all logs, ordered by date then player
            queryset = base_queryset.all().order_by('-completed_at', 'player__username')
        else:
            print(f"User {user.username} is not staff, returning only their logs.")
            # Non-staff (Player) sees only their own logs
            queryset = base_queryset.filter(player=user).order_by('-completed_at')

        print(f"Returning {queryset.count()} logs.") # Debug print
        return queryset
    # *** End modified get_queryset ***

    def perform_create(self, serializer):
        """ Set player on creation """
        serializer.save(player=self.request.user)

# *** END OF SoloSessionLogViewSet ***