from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils import timezone
import datetime
class Profile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Мужской'),
        ('F', 'Женский'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    license_accepted = models.BooleanField(default=False, verbose_name='Принимаю лицензионное соглашение')
    consent_given = models.BooleanField(default=False, verbose_name='Согласие на обработку персональных данных')
    middle_name = models.CharField(max_length=100, blank=True, verbose_name='Отчество')
    birth_date = models.DateField(null=True, blank=True, verbose_name='Дата рождения')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True, verbose_name='Пол')
    read_notifications_data = models.TextField(blank=True, default="", verbose_name="Прочитанные уведомления")


    class Meta:
        ordering = ('user',)
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


    def __str__(self):
        return self.user.username
    
class Child(models.Model):
    GENDER_CHOICES = [
        ('M', 'Мужской'),
        ('F', 'Женский'),
    ]
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='children')
    last_name = models.CharField(max_length=100, verbose_name='Фамилия')
    first_name = models.CharField(max_length=100, verbose_name='Имя')
    middle_name = models.CharField(max_length=100, blank=True, verbose_name='Отчество')
    birth_date = models.DateField(verbose_name='Дата рождения')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, verbose_name='Пол')
    # опционально: поле для связи с учётной записью ребёнка
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='child_profile')

    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()
    
class RegistrationCode(models.Model):
    # Привязываем строго к ребенку, а не к родителю
    child = models.OneToOneField('Child', on_delete=models.CASCADE, related_name='registration_code')
    code = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return timezone.now() <= self.created_at + datetime.timedelta(minutes=2)

    def __str__(self):
        return f"Код {self.code} для ребенка {self.child.first_name} (Родитель: {self.child.parent.username})"
