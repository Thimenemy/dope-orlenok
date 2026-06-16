from django.urls import path
from . import views

app_name = 'dashboard_admin'

urlpatterns = [
    path('courses/', views.admin_course_list, name='course_list'),
    path('courses/add/', views.admin_course_create, name='course_add'),
    path('courses/edit/<int:course_id>/', views.admin_course_edit, name='course_edit'),
]