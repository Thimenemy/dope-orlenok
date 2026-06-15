from django.urls import path
from . import views

app_name = 'accountant'

urlpatterns = [
    path('', views.enrollment_list, name='enrollment_list'),
    path('<int:pk>/', views.enrollment_detail, name='enrollment_detail'),
    path('financial-report/', views.finance_analytics, name='financial_report'),
    path('invoice/<int:enrollment_id>/pdf/', views.view_invoice_pdf, name='view_invoice_pdf'),
]