from django.contrib import admin
from .models import EnrollmentDocument, Enrollment


@admin.register(Enrollment)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "course",
        "parent_last_name",
        "parent_first_name",
        "parent_middle_name",
        "status",
        "created_at",
    )
    list_editable = ("status", "parent_last_name", "parent_first_name")


@admin.register(EnrollmentDocument)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "file", "document_type", "uploaded_at")
