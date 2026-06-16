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
]