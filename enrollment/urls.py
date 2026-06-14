from django.urls import path
from . import views

app_name = 'enrollment'

urlpatterns = [
    path('enroll/<int:course_id>/', views.enroll, name='enroll'),
    path('edit/<int:enrollment_id>/', views.enroll, name='edit_enrollment'),
    path('upload/<int:enrollment_id>/', views.upload_document, name='upload_document'),
    path('rework/<int:enrollment_id>/', views.rework_enrollment, name='rework_enrollment'),
    path('delete/<int:enrollment_id>/', views.delete_enrollment, name='delete_enrollment'),
    path('upload-receipt/<int:enrollment_id>/', views.upload_receipt, name='upload_receipt'),
    
]