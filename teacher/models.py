from django.db import models
from django.contrib.auth.models import User
from main.models import Course
from accounts.models import Child

class Group(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название группы')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='groups', verbose_name='Курс')
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='teaching_groups', verbose_name='Преподаватель')
    start_date = models.DateField(verbose_name='Дата начала')
    end_date = models.DateField(verbose_name='Дата окончания')
    max_students = models.PositiveSmallIntegerField(default=15, verbose_name='Максимум учеников')
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False, verbose_name='Курс завершён')

    def __str__(self):
        return f"{self.name} ({self.course.name})"

class GroupMember(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='groups')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'child')

    def __str__(self):
        return f"{self.child} в {self.group}"
    
class Schedule(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    topic = models.CharField(max_length=200, blank=True)
    room = models.CharField(max_length=50, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'start_time']
        unique_together = ['group', 'date', 'start_time']

class JournalEntry(models.Model):
    student = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='journal_entries')
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='journal_entries')
    attendance = models.BooleanField(default=False)  # Только присутствие
    comment = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('student', 'schedule')

class StudentCourseReport(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='reports')
    student = models.ForeignKey('accounts.Child', on_delete=models.CASCADE, related_name='course_reports')
    
    total_lessons = models.IntegerField(verbose_name='Всего уроков', default=0)
    attended_lessons = models.IntegerField(verbose_name='Посещено уроков', default=0)
    
    knowledge_level = models.CharField(max_length=100, verbose_name='Уровень освоения')
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'student')

    def __str__(self):
        return f"Отчёт: {self.student.first_name} по группе {self.group.name}"