from django.contrib import admin
from .models import Profile


@admin.register(Profile)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("user", "phone")
