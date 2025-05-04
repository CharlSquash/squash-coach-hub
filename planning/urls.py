# planning/urls.py
from django.urls import path
from . import views

app_name = 'planning' # Namespace for this app's URLs

urlpatterns = [
    # Session List/Detail/Live/Plan
    path('sessions/', views.session_list, name='session_list'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),
    path('session/<int:session_id>/live/', views.live_session_view, name='live_session'),
    path('session/<int:session_id>/one_page_plan/', views.one_page_plan_view, name='one_page_plan'),

    # Activity Add/Edit/Delete
    path('block/<int:block_id>/court/<int:court_num>/add/', views.add_activity, name='add_activity'),
    path('activity/<int:activity_id>/edit/', views.edit_activity, name='edit_activity'),
    path('activity/<int:activity_id>/delete/', views.delete_activity, name='delete_activity'),
    #SOLOSYNC stuff#
    path('solosync-logs/', views.solosync_log_list_view, name='solosync_log_list'),
    # Player Profile & Data Entry
    path('players/', views.players_list_view, name='players_list'),
    path('player/<int:player_id>/', views.player_profile, name='player_profile'),
    path('session/<int:session_id>/player/<int:player_id>/assess/', views.assess_player_session, name='assess_player_session'),
    path('player/<int:player_id>/add_sprint/', views.add_sprint_record, name='add_sprint_record'),
    path('player/<int:player_id>/add_volley/', views.add_volley_record, name='add_volley_record'),
    path('player/<int:player_id>/add_drive/', views.add_drive_record, name='add_drive_record'),
    path('player/<int:player_id>/add_match/', views.add_match_result, name='add_match_result'),
    path('player/<int:player_id>/assess/latest/', views.assess_latest_session_redirect, name='assess_latest_session'),
    path('assessments/pending/', views.pending_assessments_view, name='pending_assessments'),
    path('assessment/<int:assessment_id>/edit/', views.edit_session_assessment, name='edit_session_assessment'),
    path('assessment/<int:assessment_id>/delete/', views.delete_session_assessment, name='delete_session_assessment'),

    # Coach Feedback Add/Edit/Delete
    path('player/<int:player_id>/feedback/add/', views.add_coach_feedback, name='add_coach_feedback'),
    # --- NEW URLs for Feedback Edit/Delete ---
    path('feedback/<int:feedback_id>/edit/', views.edit_coach_feedback, name='edit_coach_feedback'),
    path('feedback/<int:feedback_id>/delete/', views.delete_coach_feedback, name='delete_coach_feedback'),
    
    # --- END NEW URLs ---

    # --- APIs for Manual Assignment ---
    path(
        'api/update_assignment/',
        views.update_manual_assignment_api,
        name='update_manual_assignment_api'
    ),
    path(
        'api/clear_block_assignments/<int:time_block_id>/',
        views.clear_manual_assignments_api,
        name='clear_manual_assignments_api'
    ),
]
