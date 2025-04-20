# planning/urls.py
from django.urls import path
from . import views

app_name = 'planning'

urlpatterns = [
    # Session List/Detail/Live
    path('', views.session_list, name='session_list'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),
    path('session/<int:session_id>/live/', views.live_session_view, name='live_session'),

    # One-Page Plan View (NEW)
    path(
        'session/<int:session_id>/one_page_plan/',
        views.one_page_plan_view, # New view function
        name='one_page_plan'
    ),

    # Activity Add/Edit/Delete
    path('block/<int:block_id>/court/<int:court_num>/add/', views.add_activity, name='add_activity'),
    path('activity/<int:activity_id>/edit/', views.edit_activity, name='edit_activity'),
    path('activity/<int:activity_id>/delete/', views.delete_activity, name='delete_activity'),

    # Player Profile & Data Entry
    path('player/<int:player_id>/', views.player_profile, name='player_profile'),
    path('session/<int:session_id>/player/<int:player_id>/assess/', views.assess_player_session, name='assess_player_session'),
    path('player/<int:player_id>/add_sprint/', views.add_sprint_record, name='add_sprint_record'),
    path('player/<int:player_id>/add_volley/', views.add_volley_record, name='add_volley_record'),
    path('player/<int:player_id>/add_drive/', views.add_drive_record, name='add_drive_record'),
    path('player/<int:player_id>/add_match/', views.add_match_result, name='add_match_result'),
]