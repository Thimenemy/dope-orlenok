from django.db import models
from django.urls import reverse


class Course(models.Model):
    name = models.CharField(max_length=200, db_index=True, verbose_name="Название")
    slug = models.SlugField(
        max_length=200, db_index=True, unique=True, verbose_name="URL"
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    age_min = models.PositiveSmallIntegerField(default=7, verbose_name="Мин. возраст")
    age_max = models.PositiveSmallIntegerField(default=17, verbose_name="Макс. возраст")
    duration = models.CharField(max_length=100, verbose_name="Длительность")
    format = models.CharField(
        max_length=50, verbose_name="Формат"
    )  # например, "очно", "онлайн"
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    icon = models.CharField(
        max_length=50,
        blank=True,
        default="fa-book",
        verbose_name="Иконка (класс FontAwesome)",
    )
    available = models.BooleanField(default=True, verbose_name="Доступен")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated = models.DateTimeField(auto_now=True, verbose_name="Обновлён")
    max_groups = models.PositiveIntegerField(
        default=6, verbose_name="Максимум групп на курс"
    )
    slots_per_group = models.PositiveIntegerField(
        default=15, verbose_name="Мест в одной группе"
    )
    is_finished = models.BooleanField(default=False, verbose_name="Курс завершён")

    class Meta:
        ordering = ("name",)
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "course_detail", args=[self.id, self.slug]
        )  # если нужно детальное отображение

    def get_total_slots(self):
        """Берем жесткие лимиты прямо из настроек админа, без привязки к таблице групп"""
        # Если админ поставил 6 групп по 15 мест, значит всего мест 90.
        return self.max_groups * self.slots_per_group

    def get_occupied_slots_count(self):
        """Считаем только тех, кто уже железно оплатил"""
        return self.enrollments.filter(status="paid").count()

    def get_reserve_slots_count(self):
        """Считаем тех, кто висит с квитанциями или чьи чеки проверяются"""
        return self.enrollments.filter(
            status__in=["awaiting_payment", "payment_review"]
        ).count()

    def has_free_slots(self):
        """Простая и надежная математика: если занятых + забронированных меньше чем всего мест -> места есть!"""
        total = self.get_total_slots()
        occupied_and_reserved = (
            self.get_occupied_slots_count() + self.get_reserve_slots_count()
        )
        return occupied_and_reserved < total
