import datetime
import os
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from planning.models import (
    SchoolGroup,
    Player,
    Coach,
    CoachFeedback,
    Drill,
    Session,
    TimeBlock,
    ActivityAssignment,
    ManualCourtAssignment,
    SessionAssessment,
    CourtSprintRecord,
    VolleyRecord,
    BackwallDriveRecord,
    MatchResult,
    CoachAvailability,
    CoachSessionCompletion,
    Payslip,
)

class Command(BaseCommand):
    help = 'Seeds the database with initial squash coaching data'

    def handle(self, *args, **options):
        print("Seeding School Groups...")
        group_u16a, created = SchoolGroup.objects.get_or_create(
            name="Boys U16 A",
            description="Under 16 A team players.",
            attendance_form_url="https://example.com/u16a_attendance"
        )
        group_u19b, created = SchoolGroup.objects.get_or_create(
            name="Girls U19 B",
            description="Under 19 B team players.",
            attendance_form_url="https://example.com/u19b_attendance"
        )
        group_beginner, created = SchoolGroup.objects.get_or_create(
            name="Beginner Squad",
            description="Players new to squash.",
        )

        print("Seeding Players...")
        player1, created = Player.objects.get_or_create(
            first_name="John",
            last_name="Doe",
            date_of_birth=datetime.date(2009, 5, 10),
            skill_level=Player.SkillLevel.INTERMEDIATE,
            contact_number="0821234567",
            parent_contact_number="0839876543",
            is_active=True
        )
        player1.school_groups.add(group_u16a)

        player2, created = Player.objects.get_or_create(
            first_name="Jane",
            last_name="Smith",
            date_of_birth=datetime.date(2007, 11, 22),
            skill_level=Player.SkillLevel.ADVANCED,
            contact_number="+447700900123",
            is_active=True
        )
        player2.school_groups.add(group_u19b)

        player3, created = Player.objects.get_or_create(
            first_name="Peter",
            last_name="Jones",
            skill_level=Player.SkillLevel.BEGINNER,
            contact_number="0715551122",
            is_active=True
        )
        player3.school_groups.add(group_beginner)
        player3.school_groups.add(group_u16a)

        player4, created = Player.objects.get_or_create(
            first_name="Sarah",
            last_name="Williams",
            date_of_birth=datetime.date(2008, 3, 1),
            skill_level=Player.SkillLevel.INTERMEDIATE,
            contact_number="0608883344",
            is_active=True
        )
        player4.school_groups.add(group_u19b)
        player4.school_groups.add(group_beginner)

        print("Seeding Coaches and Users...")
        user_coach1, created = User.objects.get_or_create(
            username="coach_john",
            first_name="John",
            last_name="Coach"
        )
        user_coach1.set_password("coach123")
        user_coach1.is_staff = True
        user_coach1.save()
        coach1, created = Coach.objects.get_or_create(
            user=user_coach1,
            name="John Coach",
            phone="0841112233",
            email="john.coach@example.com",
            hourly_rate=200.00,
            is_active=True
        )

        user_coach2, created = User.objects.get_or_create(
            username="coach_sue",
            first_name="Sue",
            last_name="Coaching"
        )
        user_coach2.set_password("sue456")
        user_coach2.is_staff = True
        user_coach2.save()
        coach2, created = Coach.objects.get_or_create(
            user=user_coach2,
            name="Sue Coaching",
            phone="0795556677",
            email="sue.coaching@example.com",
            hourly_rate=220.50,
            is_active=True
        )

        print("Seeding Drills...")
        drill_forehand, created = Drill.objects.get_or_create(
            name="Forehand Drive Practice",
            description="Focus on consistent forehand drives.",
            duration_minutes_default=15,
            suitable_for_any=True
        )
        drill_backhand, created = Drill.objects.get_or_create(
            name="Backhand Drive Drill",
            description="Practicing backhand drives with accuracy.",
            duration_minutes_default=15,
            suitable_for_any=True
        )
        drill_cross_court, created = Drill.objects.get_or_create(
            name="Cross Court Rally",
            description="Rallying cross court to improve length and consistency.",
            duration_minutes_default=20,
            ideal_num_players=2
        )
        drill_boast_drop, created = Drill.objects.get_or_create(
            name="Boast and Drop",
            description="Practicing the boast and follow-up drop shot.",
            duration_minutes_default=10,
            ideal_num_players=1
        )

        print("Seeding Sessions...")
        session1, created = Session.objects.get_or_create(
            session_date=timezone.now().date() + datetime.timedelta(days=2),
            session_start_time=datetime.time(16, 0, 0),
            planned_duration_minutes=90,
            school_group=group_u16a,
            notes="Focus on basic technique and court movement."
        )
        session1.attendees.add(player1, player3)
        session1.coaches_attending.add(coach1)

        session2, created = Session.objects.get_or_create(
            session_date=timezone.now().date() + datetime.timedelta(days=3),
            session_start_time=datetime.time(17, 0, 0),
            planned_duration_minutes=60,
            school_group=group_u19b,
            notes="Match play and tactical awareness."
        )
        session2.attendees.add(player2, player4)
        session2.coaches_attending.add(coach2)

        session3, created = Session.objects.get_or_create(
            session_date=timezone.now().date() + datetime.timedelta(days=5),
            session_start_time=datetime.time(15, 30, 0),
            planned_duration_minutes=75,
            school_group=group_beginner,
            notes="Introduction to basic shots and rules."
        )
        session3.attendees.add(player3, player4)
        session3.coaches_attending.add(coach1, coach2)

        print("Seeding Time Blocks for Sessions...")
        timeblock1_session1, created = TimeBlock.objects.get_or_create(
            session=session1,
            start_offset_minutes=0,
            duration_minutes=30,
            number_of_courts=2,
            block_focus="Warm-up and basic drives"
        )
        timeblock2_session1, created = TimeBlock.objects.get_or_create(
            session=session1,
            start_offset_minutes=30,
            duration_minutes=45,
            number_of_courts=2,
            rotation_interval_minutes=15,
            block_focus="Drills: Forehand & Backhand"
        )
        timeblock3_session1, created = TimeBlock.objects.get_or_create(
            session=session1,
            start_offset_minutes=75,
            duration_minutes=15,
            number_of_courts=2,
            block_focus="Cool-down"
        )

        timeblock1_session2, created = TimeBlock.objects.get_or_create(
            session=session2,
            start_offset_minutes=0,
            duration_minutes=60,
            number_of_courts=1,
            block_focus="Match Play"
        )

        print("Seeding Activity Assignments...")
        ActivityAssignment.objects.get_or_create(
            time_block=timeblock1_session1,
            court_number=1,
            drill=drill_forehand,
            duration_minutes=15,
            lead_coach=coach1,
            order=0
        )
        ActivityAssignment.objects.get_or_create(
            time_block=timeblock1_session1,
            court_number=2,
            drill=drill_backhand,
            duration_minutes=15,
            lead_coach=coach1,
            order=0
        )
        ActivityAssignment.objects.get_or_create(
            time_block=timeblock2_session1,
            court_number=1,
            drill=drill_cross_court,
            duration_minutes=30,
            lead_coach=coach1,
            order=0
        )
        ActivityAssignment.objects.get_or_create(
            time_block=timeblock2_session1,
            court_number=2,
            drill=drill_boast_drop,
            duration_minutes=30,
            lead_coach=coach1,
            order=0
        )
        ActivityAssignment.objects.get_or_create(
            time_block=timeblock1_session2,
            court_number=1,
            custom_activity_name="Practice Matches",
            duration_minutes=60,
            lead_coach=coach2,
            order=0
        )

        print("Seeding Manual Court Assignments (Example)...")
        ManualCourtAssignment.objects.get_or_create(
            time_block=timeblock2_session1,
            player=player1,
            court_number=1
        )
        ManualCourtAssignment.objects.get_or_create(
            time_block=timeblock2_session1,
            player=player3,
            court_number=2
        )

        print("Seeding Session Assessments (Example)...")
        SessionAssessment.objects.get_or_create(
            session=session1,
            player=player1,
            effort_rating=SessionAssessment.Rating.GOOD,
            focus_rating=SessionAssessment.Rating.AVERAGE,
            submitted_by=user_coach1
        )
        SessionAssessment.objects.get_or_create(
            session=session1,
            player=player3,
            effort_rating=SessionAssessment.Rating.AVERAGE,
            focus_rating=SessionAssessment.Rating.BELOW_AVERAGE,
            submitted_by=user_coach1
        )

        print("Seeding Coach Feedback (Example)...")
        CoachFeedback.objects.get_or_create(
            player=player1,
            session=session1,
            date_recorded=timezone.now(),
            strengths_observed="Good forehand consistency.",
            areas_for_development="Needs to improve backhand length.",
            suggested_focus="Practice backhand drives with a focus on depth."
        )

        print("Seeding Court Sprint Records (Example)...")
        CourtSprintRecord.objects.get_or_create(
            player=player1,
            date_recorded=timezone.now().date() - datetime.timedelta(days=7),
            duration_choice=CourtSprintRecord.DurationChoice.FIVE_MIN,
            score=25,
            session=None
        )

        print("Seeding Volley Records (Example)...")
        VolleyRecord.objects.get_or_create(
            player=player2,
            date_recorded=timezone.now().date() - datetime.timedelta(days=5),
            shot_type=VolleyRecord.ShotType.FOREHAND,
            consecutive_count=32,
            session=None
        )

        print("Seeding Backwall Drive Records (Example)...")
        BackwallDriveRecord.objects.get_or_create(
            player=player3,
            date_recorded=timezone.now().date() - datetime.timedelta(days=3),
            shot_type=BackwallDriveRecord.ShotType.BACKHAND,
            consecutive_count=18,
            session=None
        )

        print("Seeding Match Results (Example)...")
        MatchResult.objects.get_or_create(
            player=player2,
            date=timezone.now().date() - datetime.timedelta(days=1),
            opponent_name="Opponent A",
            player_score_str="3-1",
            is_competitive=False,
            session=session2
        )

        print("Seeding Coach Availability (Example)...")
        CoachAvailability.objects.get_or_create(
            coach=user_coach1,
            session=session1,
            is_available=True
        )
        CoachAvailability.objects.get_or_create(
            coach=user_coach2,
            session=session2,
            is_available=True
        )
        CoachAvailability.objects.get_or_create(
            coach=user_coach1,
            session=session2,
            is_available=False,
            notes="Unavailable due to other commitments."
        )

        print("Seeding Coach Session Completion (Example)...")
        CoachSessionCompletion.objects.get_or_create(
            coach=coach1,
            session=session1,
            assessments_submitted=True,
            confirmed_for_payment=False
        )
        CoachSessionCompletion.objects.get_or_create(
            coach=coach2,
            session=session2,
            assessments_submitted=True,
            confirmed_for_payment=True
        )

        print("Seeding Payslips (Example)...")
        Payslip.objects.get_or_create(
            coach=coach1,
            month=5,
            year=2025,
            file="payslips/2025/05/coach_john_2025_05.pdf", # Replace with actual file if you have one
            total_amount=400.00,
            generated_by=user_coach1 # Assuming the coach can generate their own for this example
        )
        Payslip.objects.get_or_create(
            coach=coach2,
            month=5,
            year=2025,
            file="payslips/2025/05/coach_sue_2025_05.pdf", # Replace with actual file
            total_amount=441.00,
            generated_by=user_coach1
        )

        print("Seed data generation complete.")

if __name__ == '__main__':
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "squash_coach_app.settings") # Make sure this matches your project's settings
    django.setup()
    # You don't need to call seed_data() here anymore,
    # the handle() method will be executed by the management command.
    pass