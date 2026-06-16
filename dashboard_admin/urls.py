from django.urls import path
from . import views

app_name = 'dashboard_admin'

urlpatterns = [
    path('courses/', views.admin_course_list, name='course_list'),
    path('courses/add/', views.admin_course_create, name='course_add'),
    path('courses/edit/<int:course_id>/', views.admin_course_edit, name='course_edit'),
    path('staff/', views.admin_staff_list, name='staff_list'),
    path('staff/add/', views.admin_staff_create, name='staff_add'),
    path('staff/edit/<int:user_id>/', views.admin_staff_edit, name='staff_edit'),
    path('staff/delete/<int:user_id>/', views.admin_staff_delete, name='staff_delete'),
    path('parents/', views.admin_parent_list, name='parent_list'),
    path('parents/add/', views.admin_parent_create, name='parent_add'),
    path('parents/edit/<int:user_id>/', views.admin_parent_edit, name='parent_edit'),
    path('parents/delete/<int:user_id>/', views.admin_parent_delete, name='parent_delete'),
    path('chats/', views.admin_chat_list, name='chat_list'),
    path('chats/create/', views.admin_chat_create, name='chat_create'),
]