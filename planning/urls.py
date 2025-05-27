# planning/urls.py

from django.urls import path
from . import views # For most of your views
from . import live_views # For the new live session features

app_name = 'planning' 

urlpatterns = [
    # --- Homepage/Dashboard URL ---
    path('dashboard/', views.homepage_view, name='homepage'),

    # --- Existing Session List/Detail/Plan ---
    path('sessions/', views.session_list, name='session_list'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),
    path('session/<int:session_id>/one_page_plan/', views.one_page_plan_view, name='one_page_plan'),

    # --- LIVE SESSION VIEW PAGE ---
    # CORRECTED: Point to live_views.live_session_page_view
    path('session/<int:session_id>/live/', live_views.live_session_page_view, name='live_session'),

    # --- Activity Add/Edit/Delete ---
    path('block/<int:block_id>/court/<int:court_num>/add/', views.add_activity, name='add_activity'),
    path('activity/<int:activity_id>/edit/', views.edit_activity, name='edit_activity'),
    path('activity/<int:activity_id>/delete/', views.delete_activity, name='delete_activity'),

    # --- Player Profile & Data Entry ---
    path('players/', views.players_list_view, name='players_list'),
    path('player/<int:player_id>/', views.player_profile, name='player_profile'),
    path('player/<int:player_id>/add_sprint/', views.add_sprint_record, name='add_sprint_record'),
    path('player/<int:player_id>/add_volley/', views.add_volley_record, name='add_volley_record'),
    path('player/<int:player_id>/add_drive/', views.add_drive_record, name='add_drive_record'),
    path('player/<int:player_id>/add_match/', views.add_match_result, name='add_match_result'),
    path('player/<int:player_id>/assess/latest/', views.assess_latest_session_redirect, name='assess_latest_session'),

    # --- Session Assessment Add/Edit/Delete ---
    path('session/<int:session_id>/player/<int:player_id>/assess/', views.assess_player_session, name='assess_player_session'),
    path('assessment/<int:assessment_id>/edit/', views.edit_session_assessment, name='edit_session_assessment'),
    path('assessment/<int:assessment_id>/delete/', views.delete_session_assessment, name='delete_session_assessment'),

    # --- Coach Feedback Add/Edit/Delete ---
    path('player/<int:player_id>/feedback/add/', views.add_coach_feedback, name='add_coach_feedback'),
    path('feedback/<int:feedback_id>/edit/', views.edit_coach_feedback, name='edit_coach_feedback'),
    path('feedback/<int:feedback_id>/delete/', views.delete_coach_feedback, name='delete_coach_feedback'),

    # --- Pending Assessments Page & Actions ---
    path('assessments/pending/', views.pending_assessments_view, name='pending_assessments'),
    path('session/<int:session_id>/mark-assessments-complete/', views.mark_my_assessments_complete_for_session_view, name='mark_my_assessments_complete'),

    # --- Coach Availability Page & Related ---
    path('my-availability/', views.my_availability_view, name='my_availability'),
    path('session-staffing/', views.session_staffing_view, name='session_staffing'),
    path('coach-completion-report/', views.coach_completion_report_view, name='coach_completion_report'),
    
    # --- Session Calendar & Export ---
    path('sessions/calendar/', views.session_calendar_view, name='session_calendar'),
    path('sessions/export-schedule/', views.export_weekly_schedule_view, name='export_weekly_schedule'),
    
    # --- API Endpoints ---
    # CORRECTED: Point to live_views.live_session_update_api
    path('api/session/<int:session_id>/live_update/', live_views.live_session_update_api, name='live_session_update_api'),
    path('api/update_assignment/', views.update_manual_assignment_api, name='update_manual_assignment_api'),
    path('api/clear_block_assignments/<int:time_block_id>/', views.clear_manual_assignments_api, name='clear_manual_assignments_api'),

    # --- SoloSync Log List ---
    path('solosync-logs/', views.solosync_log_list_view, name='solosync_log_list'),
    
    # --- Assessment Visibility Toggles ---
    path('assessment/<int:assessment_id>/toggle-visibility/', views.toggle_assessment_visibility, name='toggle_assessment_visibility'),
    path('assessment/<int:assessment_id>/toggle-superuser-review/', views.toggle_assessment_superuser_review_status, name='toggle_assessment_superuser_review_status'),

    # --- Email Confirmation ---
    path('session/<int:session_id>/confirm/<str:token>/', views.confirm_session_attendance, name='confirm_session_attendance'),
    path('session/<int:session_id>/decline/<str:token>/', views.decline_session_attendance, name='decline_session_attendance'),

    # --- Direct Dashboard Confirmation ---
    path('session/<int:session_id>/direct-confirm/', views.direct_confirm_attendance, name='direct_confirm_attendance'),
    path('session/<int:session_id>/direct-decline/', views.direct_decline_attendance, name='direct_decline_attendance'),

    # --- Bulk Availability ---
    path('set-bulk-availability/', views.set_bulk_availability_view, name='set_bulk_availability'),
]
