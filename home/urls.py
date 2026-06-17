from django.urls import path
from . import views

app_name = "home"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("schedule/", views.parent_schedule, name="parent_schedule"),  # новая страница
    path(
        "get_group_schedule/<int:group_id>/",
        views.get_group_schedule,
        name="get_group_schedule",
    ),  # AJAX
    path(
        "group_schedule/<int:group_id>/",
        views.group_schedule_page,
        name="group_schedule_page",
    ),
    path("journal/", views.parent_journal, name="parent_journal"),
    path('report/<int:report_id>/print/', views.view_report_print, name='view_report_print'),
    path('notification/read/', views.mark_notification_read_ajax, name='mark_read_ajax'),
    path('child/schedule/', views.child_schedule, name='child_schedule'),
    path('child/journal/', views.child_journal, name='child_journal'),
]
