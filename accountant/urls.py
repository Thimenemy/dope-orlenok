from django.urls import path
from . import views

app_name = 'accountant'

urlpatterns = [
    path('', views.enrollment_list, name='enrollment_list'),
    path('<int:pk>/', views.enrollment_detail, name='enrollment_detail'),
]