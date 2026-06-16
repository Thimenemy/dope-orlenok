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
        """Общая емкость курса (например, 6 групп по 15 мест = 90 мест)"""
        # Считаем количество активных групп, созданных для этого курса
        active_groups_count = self.groups.count()
        # Ограничиваем жестко до 6 групп, как в ТЗ диплома
        if active_groups_count > 6:
            active_groups_count = 6
        return active_groups_count * 15

    def get_occupied_slots_count(self):
        """Сколько мест железно занято (статус paid - оплачено)"""
        return self.enrollments.filter(status="paid").count()

    def get_reserve_slots_count(self):
        """Динамический резерв (деньги еще не пришли, но квитанции выданы)"""
        return self.enrollments.filter(
            status__in=["awaiting_payment", "payment_review"]
        ).count()

    def has_free_slots(self):
        """Проверка: остались ли физически свободные места"""
        free_slots = (
            self.get_total_slots()
            - self.get_occupied_slots_count()
            - self.get_reserve_slots_count()
        )
        return free_slots > 0
