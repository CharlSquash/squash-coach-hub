# planning/management/commands/seed_data.py

import random
import datetime
from datetime import timedelta, date, time # Import date and time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model # Import User model getter

# Import all your models from the planning app
from planning.models import (
    SchoolGroup, Player, Coach, Drill, Session, TimeBlock,
    ActivityAssignment, SessionAssessment, CourtSprintRecord,
    VolleyRecord, BackwallDriveRecord, MatchResult, CoachFeedback
)
# Import SoloSync models safely
try:
    from solosync_api.models import SoloSessionLog, SoloRoutine, SoloDrill, RoutineDrillLink, SoloSessionMetric # Import all needed
    solosync_imported = True
except ImportError:
    print("Warning: Could not import SoloSync models. SoloSync features will be disabled.")
    SoloSessionLog = None
    SoloRoutine = None
    SoloDrill = None # Define as None
    RoutineDrillLink = None # Define as None
    SoloSessionMetric = None # Define as None
    solosync_imported = False


# --- Configuration for Seed Data ---
NUM_COACHES = 3
NUM_GROUPS = 4
NUM_PLAYERS_PER_GROUP = 6
NUM_DRILLS = 15
NUM_SESSIONS_PAST = 12
NUM_SESSIONS_RECENT_FOR_REMINDER = 3
NUM_SESSIONS_FUTURE = 5
MAX_BLOCKS_PER_SESSION = 3
MAX_ACTIVITIES_PER_BLOCK_COURT = 2
ASSESSMENT_CHANCE = 0.6
FEEDBACK_CHANCE = 0.2
NUM_METRICS_PER_TYPE_PER_PLAYER = 4

# --- Sample Data Lists ---
FIRST_NAMES = ["Alex", "Ben", "Chloe", "David", "Emma", "Finn", "Grace", "Harry", "Isla", "Jack", "Kate", "Liam", "Mia", "Noah", "Olivia", "Peter", "Quinn", "Ruby", "Sam", "Tara", "Uma", "Victor", "Willow", "Xavier", "Yara", "Zoe"]
LAST_NAMES = ["Smith", "Jones", "Williams", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Garcia", "Martinez", "Robinson", "Clark"]
DRILL_FOCUS = ["Forehand Drive", "Backhand Volley", "Serve Return", "Figure 8s", "Boast & Drive", "Lob & Drop", "Ghosting", "Conditioning Game", "Length Accuracy", "Crosscourt Nick", "Match Play Simulation", "Solo Practice Routine", "Pressure Session", "Movement Drill", "Quick Feet"]
NOTES_EXAMPLES = ["Focus on hitting targets.", "Keep racquet preparation early.", "Watch the ball onto the strings.", "Emphasize split step.", "Work on recovery to the T.", "Vary pace and height."]
FEEDBACK_STRENGTHS = ["Good length on drives.", "Volleys becoming more consistent.", "Improved court movement.", "Aggressive attacking shots.", "Reads opponent well.", "Strong mental focus today."]
FEEDBACK_AREAS = ["Needs quicker recovery.", "Racquet prep on backhand.", "Watch footwork on the drop.", "Decision making under pressure.", "Serve consistency.", "Needs more variation."]
FEEDBACK_FOCUS = ["Work on boast recovery.", "Practice deep crosscourts.", "Solo hitting for consistency.", "Conditioning games.", "Watch pro matches for tactics."]

User = get_user_model() # Get the active User model

class Command(BaseCommand):
    help = 'Seeds the database with more realistic sample data for the planning app.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Deleting old data...")
        # Order matters for deletion due to dependencies
        ActivityAssignment.objects.all().delete()
        TimeBlock.objects.all().delete()
        SessionAssessment.objects.all().delete()
        CoachFeedback.objects.all().delete()
        CourtSprintRecord.objects.all().delete()
        VolleyRecord.objects.all().delete()
        BackwallDriveRecord.objects.all().delete()
        MatchResult.objects.all().delete()
        try:
            from planning.models import ManualCourtAssignment
            ManualCourtAssignment.objects.all().delete()
        except ImportError: pass
        # Delete SoloSync data if models exist
        if solosync_imported:
            try:
                # Models already imported if solosync_imported is True
                SoloSessionMetric.objects.all().delete()
                SoloSessionLog.objects.all().delete()
                RoutineDrillLink.objects.all().delete()
                SoloRoutine.objects.all().delete()
                SoloDrill.objects.all().delete()
            except Exception as e:
                 print(f"Warning: Error deleting SoloSync data - {e}")
        # Delete core planning data
        Session.objects.all().delete()
        Player.objects.all().delete()
        SchoolGroup.objects.all().delete()
        Drill.objects.all().delete() # Assuming this is planning.Drill
        Coach.objects.all().delete()

        self.stdout.write("Creating new data...")

        # --- Create a default User (if none exists) to assign as creator ---
        # Or fetch an existing superuser
        default_user, created = User.objects.get_or_create(
            username='coach_admin', # Or your superuser username
            defaults={'is_staff': True, 'is_superuser': True}
        )
        if created:
             default_user.set_password('password') # Set a default password if created
             default_user.save()
             self.stdout.write(f"Created default user '{default_user.username}'")


        # Create Coaches (These are separate from Users for now)
        coaches = [Coach.objects.create(name=f"Coach {chr(65+i)}") for i in range(NUM_COACHES)]
        self.stdout.write(f"Created {len(coaches)} coaches.")

        # Create School Groups
        groups = []
        group_levels = ["U19 Boys", "U19 Girls", "U16 Boys", "U16 Girls", "Development"]
        for i in range(NUM_GROUPS):
            name = f"{random.choice(group_levels)} {chr(65+i)}"
            group = SchoolGroup.objects.create(name=name)
            groups.append(group)
        self.stdout.write(f"Created {len(groups)} school groups.")

        # Create Planning Drills
        planning_drills = [
            Drill.objects.create(
                name=f"{random.choice(DRILL_FOCUS)} Drill #{i+1}",
                description=f"Focuses on {random.choice(DRILL_FOCUS).lower()}.",
                duration_minutes_default=random.choice([10, 15, 20]),
                ideal_num_players=random.choice([None, 1, 2, 3, 4]),
                suitable_for_any=random.choice([True, False])
            ) for i in range(NUM_DRILLS)
        ]
        self.stdout.write(f"Created {len(planning_drills)} planning drills.")

        # Create Players (Assuming Player model is separate from User)
        all_players = []
        for group in groups:
            for i in range(NUM_PLAYERS_PER_GROUP):
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                player = Player.objects.create(
                    first_name=first,
                    last_name=f"{last} {group.name.split()[0][0]}{i+1}",
                    skill_level=random.choice(Player.SkillLevel.values),
                    is_active=True
                )
                player.school_groups.add(group)
                all_players.append(player)
        self.stdout.write(f"Created {len(all_players)} players.")

        # Create Sessions
        all_sessions = []
        today = timezone.now().date()
        base_time = time(15, 0) # 3 PM
        session_dates_past = []
        for i in range(NUM_SESSIONS_RECENT_FOR_REMINDER):
             session_dates_past.append(today - timedelta(days=random.randint(1, 6)))
        for i in range(NUM_SESSIONS_PAST - NUM_SESSIONS_RECENT_FOR_REMINDER):
            session_dates_past.append(today - timedelta(days=random.randint(7, 60)))

        past_sessions_created = []
        for i, session_date in enumerate(session_dates_past):
            random_hour_offset = random.randint(-2, 2); random_minute_offset = random.randint(0, 59)
            temp_dt = datetime.datetime.combine(session_date, base_time) + timedelta(hours=random_hour_offset, minutes=random_minute_offset)
            session_start_time = temp_dt.time()
            group = random.choice(groups)
            is_complete = (session_date < (today - timedelta(days=7))) and (random.random() > 0.4)
            session = Session.objects.create(
                session_date=session_date, session_start_time=session_start_time,
                planned_duration_minutes=random.choice([60, 75, 90]), school_group=group,
                notes=f"Past session focusing on {random.choice(DRILL_FOCUS).lower()}.", assessments_complete=is_complete
            )
            session.coaches_attending.add(random.choice(coaches))
            attendees_for_session = list(group.players.filter(is_active=True))
            if attendees_for_session:
                num_attendees = random.randint(max(1, len(attendees_for_session)-3), len(attendees_for_session))
                session.attendees.set(random.sample(attendees_for_session, num_attendees))
            all_sessions.append(session)
            past_sessions_created.append(session)

        for i in range(NUM_SESSIONS_FUTURE):
            session_date = today + timedelta(days=random.randint(1, 30))
            random_hour_offset = random.randint(-2, 2); random_minute_offset = random.randint(0, 59)
            temp_dt = datetime.datetime.combine(session_date, base_time) + timedelta(hours=random_hour_offset, minutes=random_minute_offset)
            session_start_time = temp_dt.time()
            group = random.choice(groups)
            session = Session.objects.create(
                session_date=session_date, session_start_time=session_start_time,
                planned_duration_minutes=random.choice([60, 75, 90]), school_group=group,
                notes=f"Upcoming session focusing on {random.choice(DRILL_FOCUS).lower()}."
            )
            session.coaches_attending.add(random.choice(coaches))
            all_sessions.append(session)
        self.stdout.write(f"Created {len(all_sessions)} sessions.")

        # Create TimeBlocks and Activities
        for session in all_sessions:
            session_duration = session.planned_duration_minutes; num_blocks = random.randint(1, MAX_BLOCKS_PER_SESSION)
            block_duration = session_duration // num_blocks; current_offset = 0
            for i in range(num_blocks):
                actual_duration = block_duration if i < num_blocks - 1 else session_duration - current_offset
                if actual_duration <= 0: continue
                num_courts = random.randint(1, 3)
                block = TimeBlock.objects.create(
                    session=session, start_offset_minutes=current_offset, duration_minutes=actual_duration,
                    number_of_courts=num_courts, rotation_interval_minutes=random.choice([None, 10, 15, 20]) if actual_duration > 15 else None,
                    block_focus=random.choice(DRILL_FOCUS)
                )
                current_offset += actual_duration
                for court in range(1, num_courts + 1):
                    num_activities = random.randint(0, MAX_ACTIVITIES_PER_BLOCK_COURT)
                    activity_duration = actual_duration // max(1, num_activities) if num_activities > 0 else actual_duration
                    for act_order in range(num_activities):
                        use_drill = random.choice([True, True, False])
                        ActivityAssignment.objects.create(
                            time_block=block, court_number=court,
                            drill=random.choice(planning_drills) if use_drill else None,
                            custom_activity_name=f"Custom Focus {act_order+1}" if not use_drill else "",
                            duration_minutes=activity_duration,
                            lead_coach=random.choice(coaches) if random.random() > 0.5 else None,
                            order=act_order, activity_notes=random.choice(NOTES_EXAMPLES) if random.random() > 0.7 else ""
                        )
        self.stdout.write("Created TimeBlocks and Activities.")

        # Create Assessments and Feedback for past sessions
        for session in past_sessions_created:
            attendees = list(session.attendees.all())
            for player in attendees:
                if random.random() < ASSESSMENT_CHANCE and not session.assessments_complete:
                    SessionAssessment.objects.create(
                        session=session, player=player, date_recorded=session.session_date,
                        effort_rating=random.randint(1, 5), focus_rating=random.randint(1, 5),
                        resilience_rating=random.randint(1, 5), composure_rating=random.randint(1, 5),
                        decision_making_rating=random.randint(1, 5),
                        coach_notes=random.choice(NOTES_EXAMPLES) if random.random() > 0.5 else ""
                    )
                if random.random() < FEEDBACK_CHANCE:
                     CoachFeedback.objects.create(
                         player=player, session=session if random.random() > 0.3 else None,
                         strengths_observed=random.choice(FEEDBACK_STRENGTHS),
                         areas_for_development=random.choice(FEEDBACK_AREAS),
                         suggested_focus=random.choice(FEEDBACK_FOCUS) if random.random() > 0.5 else "",
                         general_notes=random.choice(NOTES_EXAMPLES) if random.random() > 0.8 else ""
                     )
        self.stdout.write("Created Assessments and Feedback.")

        # --- Create Multiple Metric Records Per Player ---
        self.stdout.write("Creating Metric Records...")
        min_date = today - timedelta(days=90)
        date_range_days = (today - min_date).days
        for player in all_players:
            for i in range(NUM_METRICS_PER_TYPE_PER_PLAYER):
                record_date = min_date + timedelta(days=random.randint(0, date_range_days))
                CourtSprintRecord.objects.create(
                    player=player, date_recorded=record_date, duration_choice=random.choice(CourtSprintRecord.DurationChoice.values),
                    score=max(0, random.randint(15, 35) + int(player.skill_level == Player.SkillLevel.ADVANCED)*3 - int(player.skill_level == Player.SkillLevel.BEGINNER)*3),
                    session=random.choice(past_sessions_created) if random.random() > 0.6 else None )
            for i in range(NUM_METRICS_PER_TYPE_PER_PLAYER):
                record_date = min_date + timedelta(days=random.randint(0, date_range_days))
                fh_count = max(0, random.randint(5, 50) + int(player.skill_level == Player.SkillLevel.ADVANCED)*5 - int(player.skill_level == Player.SkillLevel.BEGINNER)*5)
                VolleyRecord.objects.create( player=player, date_recorded=record_date, shot_type=VolleyRecord.ShotType.FOREHAND, consecutive_count=fh_count, session=random.choice(past_sessions_created) if random.random() > 0.8 else None )
                record_date = min_date + timedelta(days=random.randint(0, date_range_days))
                bh_count = max(0, random.randint(4, 45) + int(player.skill_level == Player.SkillLevel.ADVANCED)*5 - int(player.skill_level == Player.SkillLevel.BEGINNER)*5)
                VolleyRecord.objects.create( player=player, date_recorded=record_date, shot_type=VolleyRecord.ShotType.BACKHAND, consecutive_count=bh_count, session=random.choice(past_sessions_created) if random.random() > 0.8 else None )
            for i in range(NUM_METRICS_PER_TYPE_PER_PLAYER):
                record_date = min_date + timedelta(days=random.randint(0, date_range_days))
                fh_drive_count = max(0, random.randint(8, 60) + int(player.skill_level == Player.SkillLevel.ADVANCED)*7 - int(player.skill_level == Player.SkillLevel.BEGINNER)*7)
                BackwallDriveRecord.objects.create( player=player, date_recorded=record_date, shot_type=BackwallDriveRecord.ShotType.FOREHAND, consecutive_count=fh_drive_count, session=random.choice(past_sessions_created) if random.random() > 0.8 else None )
                record_date = min_date + timedelta(days=random.randint(0, date_range_days))
                bh_drive_count = max(0, random.randint(6, 55) + int(player.skill_level == Player.SkillLevel.ADVANCED)*7 - int(player.skill_level == Player.SkillLevel.BEGINNER)*7)
                BackwallDriveRecord.objects.create( player=player, date_recorded=record_date, shot_type=BackwallDriveRecord.ShotType.BACKHAND, consecutive_count=bh_drive_count, session=random.choice(past_sessions_created) if random.random() > 0.8 else None )
            for i in range(NUM_METRICS_PER_TYPE_PER_PLAYER // 2):
                 record_date = min_date + timedelta(days=random.randint(0, date_range_days))
                 MatchResult.objects.create( player=player, date=record_date, opponent_name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}", player_score_str=f"{random.randint(0,3)}", opponent_score_str=f"{random.randint(0,3)}", is_competitive=random.choice([True, False, False]), match_notes="Close match." if random.random() > 0.5 else "", session=random.choice(past_sessions_created) if random.random() > 0.5 else None )
        self.stdout.write(f"Created multiple metric/match records for {len(all_players)} players.")

        # --- Seed SoloSync Data (if models were imported) ---
        if solosync_imported and SoloDrill is not None and SoloRoutine is not None and RoutineDrillLink is not None and SoloSessionLog is not None:
            self.stdout.write("Creating SoloSync Data...")
            # Create Solo Drills
            solo_drills = [
                SoloDrill.objects.create(
                    name=f"Solo {focus} Focus",
                    description=f"Solo practice for {focus.lower()}",
                    created_by=default_user # Assign the default User
                )
                for focus in ["Drives", "Volleys", "Drops", "Boasts", "Length", "Movement"]
            ]

            # Create Solo Routines
            solo_routines = []
            for i in range(5): # Create 5 routines
                routine = SoloRoutine.objects.create(
                    name=f"Solo Routine {i+1}",
                    description=f"Routine focusing on {random.choice(DRILL_FOCUS).lower()}",
                    created_by=default_user # Assign the default User
                )
                # Add steps (RoutineDrillLink)
                num_steps = random.randint(3, 6)
                for step_order in range(num_steps):
                    RoutineDrillLink.objects.create(
                        routine=routine,
                        drill=random.choice(solo_drills),
                        order=step_order + 1,
                        duration_minutes=random.choice([3, 5, 7, 10]),
                        difficulty_rating=random.randint(1, 5),
                        rest_after_seconds=random.choice([30, 45, 60]),
                        notes=f"Focus point for step {step_order+1}: {random.choice(NOTES_EXAMPLES)}",
                        metrics_to_collect=random.sample(["count", "accuracy", "time"], k=random.randint(0,2))
                    )
                routine.save() # Recalculate total duration after adding links
                solo_routines.append(routine)
                # Assign to some players (assuming Player model is NOT the User model)
                # If Player IS your User model, use User objects instead of Player objects here
                players_to_assign_qs = Player.objects.filter(pk__in=random.sample([p.id for p in all_players], k=random.randint(2, 5)))
                # We need to assign USER objects to assigned_players M2M field if it points to AUTH_USER_MODEL
                # This requires linking Player to User or assuming User objects exist with corresponding players
                # For now, let's skip assigning players if Player != User model to avoid complexity
                # If Player IS the User model, this would work:
                # routine.assigned_players.set(players_to_assign_qs)

            self.stdout.write(f"Created {len(solo_routines)} Solo Routines with steps.")

            # Create Solo Session Logs (Assuming Player IS the User model for simplicity here)
            # If Player is separate, you need a way to link Player to User in the log
            num_logs_to_create = len(all_players) * 2
            users_for_logs = User.objects.filter(is_staff=False, is_superuser=False)[:len(all_players)] # Get some non-staff users
            if users_for_logs:
                for _ in range(num_logs_to_create):
                    user_player = random.choice(users_for_logs) # Use User model instance
                    routine = random.choice(solo_routines)
                    completion_date_dt = timezone.make_aware(
                        datetime.datetime.combine(
                            today - timedelta(days=random.randint(0, 30)),
                            time(random.randint(6, 20), random.randint(0, 59))
                        )
                    )
                    SoloSessionLog.objects.create(
                        player=user_player, # Assign User instance
                        routine=routine,
                        completion_date=completion_date_dt,
                        physical_difficulty_rating=random.randint(1, 5),
                        session_notes=f"Completed {routine.name}. Felt {random.choice(['good', 'tired', 'focused', 'distracted'])}."
                    )
                self.stdout.write(f"Created {num_logs_to_create} Solo Session Logs.")
            else:
                 self.stdout.write("Warning: Could not create SoloSessionLogs as no non-staff users found.")


        self.stdout.write(self.style.SUCCESS('Successfully seeded database!'))

