# planning/management/commands/seed_data.py
import random
from datetime import date, timedelta, time

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
# Import models from the 'planning' app.
from planning.models import (
    SchoolGroup, Player, Coach, Session, TimeBlock,
    ActivityAssignment, SessionAssessment, CourtSprintRecord,
    VolleyRecord, BackwallDriveRecord, MatchResult,
    ManualCourtAssignment, CoachAvailability, CoachSessionCompletion,
    Drill, Payslip, Venue # Added Venue
)

User = get_user_model()

# --- Names/Usernames used by the seed script ---
SEED_COACH_USERNAMES = ['coach_a', 'coach_b', 'coach_c']
SEED_COACH_NAMES = ['Alice Smith', 'Bob Johnson', 'Carol Davis'] 
SEED_PLAYER_NAMES = [('John', 'Doe'), ('Jane', 'Roe'), ('Mike', 'Lane'), ('Sara', 'Dane')]
SEED_GROUP_NAMES = ['U19 Boys Squad', 'U16 Girls Team']
SEED_VENUE_NAMES = ['Main Courts', 'Court 3', 'School Hall']
SEED_DRILL_NAMES = [
    ("Forehand Drives (Rails)", "Focus on hitting consistent forehand drives down the wall.", 10),
    ("Backhand Volleys (Cross-court)", "Practice short, sharp backhand cross-court volleys.", 10),
    ("Ghosting (3 Corners)", "Movement drill covering front two corners and back T.", 5),
    ("Conditioning Game (Full Court)", "High-intensity game to build stamina.", 15),
    ("Serve Practice (Targets)", "Focus on accurate serves to specific targets.", 10)
]


def clear_targeted_data_logic():
    print("Clearing specific seeded data...")
    # Delete in reverse order of dependencies or use cascade if set up
    Payslip.objects.filter(coach__name__in=SEED_COACH_NAMES).delete() # More targeted
    CoachSessionCompletion.objects.filter(coach__name__in=SEED_COACH_NAMES).delete()
    CoachAvailability.objects.filter(coach__username__in=SEED_COACH_USERNAMES).delete()
    
    # For SessionAssessment, ActivityAssignment, ManualCourtAssignment, TimeBlock
    # we need to identify sessions created by the seed script.
    # If sessions have a note like "SEED_SESSION:", we can use that.
    seeded_sessions = Session.objects.filter(notes__icontains="SEED_SESSION:")
    SessionAssessment.objects.filter(session__in=seeded_sessions).delete()
    ActivityAssignment.objects.filter(time_block__session__in=seeded_sessions).delete()
    ManualCourtAssignment.objects.filter(time_block__session__in=seeded_sessions).delete()
    TimeBlock.objects.filter(session__in=seeded_sessions).delete()
    seeded_sessions.delete() # Now delete the sessions themselves

    Drill.objects.filter(name__in=[d[0] for d in SEED_DRILL_NAMES]).delete()
    
    for first, last in SEED_PLAYER_NAMES:
        Player.objects.filter(first_name=first, last_name=last).delete()
    print(f"Deleted specific players: {SEED_PLAYER_NAMES}")

    SchoolGroup.objects.filter(name__in=SEED_GROUP_NAMES).delete()
    print(f"Deleted specific school groups: {SEED_GROUP_NAMES}")
    
    Venue.objects.filter(name__in=SEED_VENUE_NAMES).delete()
    print(f"Deleted specific venues: {SEED_VENUE_NAMES}")

    Coach.objects.filter(user__username__in=SEED_COACH_USERNAMES).delete()
    print(f"Deleted Coach profiles for users: {SEED_COACH_USERNAMES}")

    User.objects.filter(username__in=SEED_COACH_USERNAMES, is_superuser=False).delete()
    print(f"Deleted User accounts: {SEED_COACH_USERNAMES}")
    
    print("Targeted data clearing finished.")


def seed_data_logic():
    print("Starting to seed data...")

    # --- 0. Create Venues ---
    venue_main, _ = Venue.objects.update_or_create(name="Main Courts", defaults={'is_active': True})
    venue_c3, _ = Venue.objects.update_or_create(name="Court 3", defaults={'is_active': True})
    venue_hall, _ = Venue.objects.update_or_create(name="School Hall (Fitness)", defaults={'is_active': True})
    print("Created/updated venues.")

    # --- 1. Create Users and Coaches ---
    try:
        superuser = User.objects.get(username='admin') 
        print(f"Superuser '{superuser.username}' found.")
    except User.DoesNotExist:
        print("Superuser 'admin' not found. Please create one manually via createsuperuser or adjust script.")
        superuser = None

    user_coach_a, created_a = User.objects.get_or_create(
        username='coach_a', 
        defaults={'first_name': 'Alice', 'last_name': 'Smith', 'email': 'alice@example.com', 'is_staff': True}
    )
    if created_a: user_coach_a.set_password('password'); user_coach_a.save()
    coach_a, _ = Coach.objects.update_or_create(user=user_coach_a, defaults={'name': 'Alice Smith', 'hourly_rate': 100.00, 'is_active': True})
    print(f"Created/found Coach A: {coach_a.name}")

    user_coach_b, created_b = User.objects.get_or_create(
        username='coach_b', 
        defaults={'first_name': 'Bob', 'last_name': 'Johnson', 'email': 'bob@example.com', 'is_staff': True}
    )
    if created_b: user_coach_b.set_password('password'); user_coach_b.save()
    coach_b, _ = Coach.objects.update_or_create(user=user_coach_b, defaults={'name': 'Bob Johnson', 'hourly_rate': 110.00, 'is_active': True})
    print(f"Created/found Coach B: {coach_b.name}")

    user_coach_c, created_c = User.objects.get_or_create(
        username='coach_c', 
        defaults={'first_name': 'Carol', 'last_name': 'Davis', 'email': 'carol@example.com', 'is_staff': True}
    )
    if created_c: user_coach_c.set_password('password'); user_coach_c.save()
    coach_c, _ = Coach.objects.update_or_create(user=user_coach_c, defaults={'name': 'Carol Davis', 'hourly_rate': 105.00, 'is_active': True})
    print(f"Created/found Coach C: {coach_c.name}")

    # --- 2. Create School Groups ---
    group_u19, _ = SchoolGroup.objects.update_or_create(name='U19 Boys Squad')
    group_u16, _ = SchoolGroup.objects.update_or_create(name='U16 Girls Team')
    print("Created/updated school groups.")

    # --- 3. Create Players ---
    player1, _ = Player.objects.update_or_create(first_name='John', last_name='Doe', defaults={'skill_level': Player.SkillLevel.INTERMEDIATE, 'is_active': True})
    player1.school_groups.set([group_u19])
    player2, _ = Player.objects.update_or_create(first_name='Jane', last_name='Roe', defaults={'skill_level': Player.SkillLevel.ADVANCED, 'is_active': True})
    player2.school_groups.set([group_u19])
    player3, _ = Player.objects.update_or_create(first_name='Mike', last_name='Lane', defaults={'skill_level': Player.SkillLevel.BEGINNER, 'is_active': True})
    player3.school_groups.set([group_u16])
    player4, _ = Player.objects.update_or_create(first_name='Sara', last_name='Dane', defaults={'skill_level': Player.SkillLevel.INTERMEDIATE, 'is_active': True})
    player4.school_groups.set([group_u16])
    print("Created/updated players and assigned to groups.")
    
    # --- Create Drills ---
    drills = {}
    for drill_name, drill_desc, drill_dur in SEED_DRILL_NAMES:
        drill, _ = Drill.objects.update_or_create(
            name=drill_name,
            defaults={'description': drill_desc, 'duration_minutes_default': drill_dur}
        )
        drills[drill_name] = drill
    print("Created/updated drills.")


    # --- 4. Create Sessions with TimeBlocks and Activities ---
    today_date = timezone.now().date()
    
    # Session 1 (Past, Coach A & B attending)
    session1_date = today_date - timedelta(days=7)
    session1, _ = Session.objects.update_or_create(
        session_date=session1_date,
        session_start_time=time(14, 0, 0),
        school_group=group_u19, 
        defaults={
            'planned_duration_minutes': 90, 'venue': venue_main, 
            'notes': 'SEED_SESSION: Focus on match play tactics.'
        }
    )
    session1.coaches_attending.set([coach_a, coach_b])
    session1.attendees.set([player1, player2])
    # TimeBlocks for Session 1
    tb1_s1, _ = TimeBlock.objects.update_or_create(session=session1, start_offset_minutes=0, defaults={'duration_minutes': 30, 'number_of_courts': 2, 'block_focus': 'Warm-up & Ghosting', 'rotation_interval_minutes': 10})
    ActivityAssignment.objects.update_or_create(time_block=tb1_s1, court_number=1, order=0, defaults={'drill': drills["Ghosting (3 Corners)"], 'duration_minutes': 10})
    ActivityAssignment.objects.update_or_create(time_block=tb1_s1, court_number=2, order=0, defaults={'custom_activity_name': 'Dynamic Warm-up', 'duration_minutes': 10})
    ActivityAssignment.objects.update_or_create(time_block=tb1_s1, court_number=1, order=1, defaults={'custom_activity_name': 'Light Hitting', 'duration_minutes': 20}) # Follows ghosting
    
    tb2_s1, _ = TimeBlock.objects.update_or_create(session=session1, start_offset_minutes=30, defaults={'duration_minutes': 60, 'number_of_courts': 2, 'block_focus': 'Match Play Scenarios'})
    ActivityAssignment.objects.update_or_create(time_block=tb2_s1, court_number=1, order=0, defaults={'drill': drills["Conditioning Game (Full Court)"], 'duration_minutes': 25})
    ActivityAssignment.objects.update_or_create(time_block=tb2_s1, court_number=2, order=0, defaults={'custom_activity_name': 'King of the Court', 'duration_minutes': 25})
    # Manual assignment for Session 1, TimeBlock 1
    ManualCourtAssignment.objects.update_or_create(time_block=tb1_s1, player=player1, defaults={'court_number': 1})
    ManualCourtAssignment.objects.update_or_create(time_block=tb1_s1, player=player2, defaults={'court_number': 2})
    print(f"Created/updated Session 1 with TimeBlocks and Activities.")

    # Session 2 (Past, Coach B & C attending)
    session2_date = today_date - timedelta(days=3)
    session2, _ = Session.objects.update_or_create(
        session_date=session2_date,
        session_start_time=time(16, 0, 0),
        school_group=group_u16,
        defaults={
            'planned_duration_minutes': 60, 'venue': venue_c3, 
            'notes': 'SEED_SESSION: Basic drills and fitness.'
        }
    )
    session2.coaches_attending.set([coach_b, coach_c])
    session2.attendees.set([player3, player4])
    # TimeBlocks for Session 2
    tb1_s2, _ = TimeBlock.objects.update_or_create(session=session2, start_offset_minutes=0, defaults={'duration_minutes': 20, 'number_of_courts': 1, 'block_focus': 'Forehand Technique'})
    ActivityAssignment.objects.update_or_create(time_block=tb1_s2, court_number=1, order=0, defaults={'drill': drills["Forehand Drives (Rails)"], 'duration_minutes': 20})
    tb2_s2, _ = TimeBlock.objects.update_or_create(session=session2, start_offset_minutes=20, defaults={'duration_minutes': 20, 'number_of_courts': 1, 'block_focus': 'Backhand Volleys'})
    ActivityAssignment.objects.update_or_create(time_block=tb2_s2, court_number=1, order=0, defaults={'drill': drills["Backhand Volleys (Cross-court)"], 'duration_minutes': 20})
    tb3_s2, _ = TimeBlock.objects.update_or_create(session=session2, start_offset_minutes=40, defaults={'duration_minutes': 20, 'number_of_courts': 1, 'block_focus': 'Serve Practice', 'rotation_interval_minutes': 5}) # Added rotation
    ActivityAssignment.objects.update_or_create(time_block=tb3_s2, court_number=1, order=0, defaults={'drill': drills["Serve Practice (Targets)"], 'duration_minutes': 10})
    ActivityAssignment.objects.update_or_create(time_block=tb3_s2, court_number=1, order=1, defaults={'custom_activity_name': 'Return of Serve Drill', 'duration_minutes': 10})
    print(f"Created/updated Session 2 with TimeBlocks and Activities.")

    # Session 3 (Today, Coach A attending)
    session3, _ = Session.objects.update_or_create(
        session_date=today_date,
        session_start_time=time(10, 0, 0),
        school_group=group_u19,
        defaults={
            'planned_duration_minutes': 75, 'venue': venue_main, 
            'notes': 'SEED_SESSION: Match practice.'
        }
    )
    session3.coaches_attending.set([coach_a])
    session3.attendees.set([player1])
    # TimeBlocks for Session 3
    tb1_s3, _ = TimeBlock.objects.update_or_create(session=session3, start_offset_minutes=0, defaults={'duration_minutes': 75, 'number_of_courts': 1, 'block_focus': 'Full Match Play'})
    ActivityAssignment.objects.update_or_create(time_block=tb1_s3, court_number=1, order=0, defaults={'custom_activity_name': 'Conditioned Games', 'duration_minutes': 75})
    print(f"Created/updated Session 3 with TimeBlocks and Activities.")

    # --- 5. Create Session Assessments (linked to seeded sessions/players/coaches) ---
    SessionAssessment.objects.update_or_create(
        session=session1, player=player1, submitted_by=user_coach_a,
        defaults={
            'effort_rating': SessionAssessment.Rating.GOOD, 'focus_rating': SessionAssessment.Rating.AVERAGE,
            'coach_notes': 'SEED_ASSESSMENT: Good effort by John in session 1.', 'date_recorded': session1_date
        }
    )
    print(f"Created/updated assessment by Coach A for Player 1 in Session 1.")

    SessionAssessment.objects.update_or_create(
        session=session2, player=player3, submitted_by=user_coach_c,
        defaults={
            'effort_rating': SessionAssessment.Rating.EXCELLENT,
            'coach_notes': 'SEED_ASSESSMENT: Mike showed great focus.', 'date_recorded': session2_date
        }
    )
    print(f"Created/updated assessment by Coach C for Player 3 in Session 2.")

    # --- 6. Create CoachSessionCompletion Records ---
    CoachSessionCompletion.objects.update_or_create(
        coach=coach_a, session=session1,
        defaults={'assessments_submitted': True, 'confirmed_for_payment': False}
    )
    print(f"Updated Coach A as assessments_submitted=True for Session 1.")

    csc_s1_cb, _ = CoachSessionCompletion.objects.update_or_create(
        coach=coach_b, session=session1,
        defaults={'assessments_submitted': False, 'confirmed_for_payment': False}
    )
    print(f"Updated Coach B has assessments_submitted=False for Session 1.")

    csc_s2_cb, _ = CoachSessionCompletion.objects.update_or_create(
        coach=coach_b, session=session2,
        defaults={'assessments_submitted': False, 'confirmed_for_payment': False}
    )
    print(f"Updated Coach B has assessments_submitted=False for Session 2.")

    CoachSessionCompletion.objects.update_or_create(
        coach=coach_c, session=session2,
        defaults={'assessments_submitted': True, 'confirmed_for_payment': False}
    )
    print(f"Updated Coach C as assessments_submitted=True for Session 2.")

    print("Seed data creation/update completed successfully!")


class Command(BaseCommand):
    help = 'Seeds the database with initial data for the planning app, or clears specific seeded data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear_seeded', 
            action='store_true',
            help='Clear specific data known to be created by this seed script. Use with caution.',
        )
        parser.add_argument(
            '--seed', 
            action='store_true',
            help='Run the seeding process.',
        )

    def handle(self, *args, **options):
        if not options['clear_seeded'] and not options['seed']:
            self.stdout.write(self.style.WARNING("Please specify an action: --seed or --clear_seeded"))
            return

        if options['clear_seeded']:
            self.stdout.write(self.style.WARNING(
                "Attempting to clear specific seeded data. "
                "This assumes your manually entered data does NOT use the exact same unique identifiers "
                "(usernames, names for coaches/groups/players/venues/drills) as the seed script."
            ))
            confirm = input("Are you sure you want to clear specific seeded data? (yes/no): ")
            if confirm.lower() == 'yes':
                clear_targeted_data_logic()
                self.stdout.write(self.style.SUCCESS("Specific seeded data clearing process finished."))
            else:
                self.stdout.write("Seeded data clearing aborted by user.")
        
        if options['seed']:
            self.stdout.write("Seeding data...")
            seed_data_logic()
            self.stdout.write(self.style.SUCCESS("Data seeding completed successfully."))
