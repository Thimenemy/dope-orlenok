from django.contrib import admin
from .models import Course

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'age_min', 'age_max', 'duration', 'price', 'available', 'created')
    list_filter = ('available', 'created', 'updated')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('price', 'available')