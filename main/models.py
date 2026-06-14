from django.db import models
from django.urls import reverse

class Course(models.Model):
    name = models.CharField(max_length=200, db_index=True, verbose_name='Название')
    slug = models.SlugField(max_length=200, db_index=True, unique=True, verbose_name='URL')
    description = models.TextField(blank=True, verbose_name='Описание')
    age_min = models.PositiveSmallIntegerField(default=7, verbose_name='Мин. возраст')
    age_max = models.PositiveSmallIntegerField(default=17, verbose_name='Макс. возраст')
    duration = models.CharField(max_length=100, verbose_name='Длительность')
    format = models.CharField(max_length=50, verbose_name='Формат')  # например, "очно", "онлайн"
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    icon = models.CharField(max_length=50, blank=True, default='fa-book', verbose_name='Иконка (класс FontAwesome)')
    available = models.BooleanField(default=True, verbose_name='Доступен')
    created = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated = models.DateTimeField(auto_now=True, verbose_name='Обновлён')

    class Meta:
        ordering = ('name',)
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('course_detail', args=[self.id, self.slug])  # если нужно детальное отображение