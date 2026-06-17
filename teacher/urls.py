from django.urls import path
from . import views

app_name = "teacher"

urlpatterns = [
    path("groups/", views.group_list, name="group_list"),
    path("group/<int:pk>/", views.group_detail, name="group_detail"),
    path(
        "group/<int:pk>/generate_schedule/",
        views.generate_schedule_group,
        name="generate_schedule_group",
    ),
    path(
        "update_cell/<int:group_id>/<str:date>/", views.update_cell, name="update_cell"
    ),
    path("save_all_changes/<int:pk>/", views.save_all_changes, name="save_all_changes"),
   path('group/<int:pk>/chat/', views.group_chat_redirect, name='group_chat_redirect'),
   path('group/<int:group_id>/create_group_chat/', views.create_group_chat_for_group, name='create_group_chat_for_group'),
   path('group/<int:group_id>/complete/', views.complete_course, name='complete_course'),
   path('reports/', views.reports_list, name='reports_list'),
   path("course/<int:group_id>/finish/", views.complete_course, name="finish_course"),
   
]
