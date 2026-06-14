from django.db import models
from django.contrib.auth.models import User
from main.models import Course


from django.db import models
from django.contrib.auth.models import User
from main.models import Course
from accounts.models import Child   # добавьте импорт

class Enrollment(models.Model):
    STATUS_CHOICES = [
        ("waiting_docs", "Ожидание документов"),
        ("under_review", "На проверке"),
        ("submitted", "Ожидание"),
        ("approved", "Одобрена"),
        ('awaiting_payment', 'Ожидает оплаты'),
        ('payment_review', 'Ожидает проверки оплаты'),
        ("paid", "Оплачена"),
        ("rejected", "Отклонена"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="enrollments", null=True, blank=True)  # связь с ребёнком

    # Данные родителя (можно брать из user, но для снэпшота оставить)
    parent_last_name = models.CharField(max_length=100, verbose_name="Фамилия родителя")
    parent_first_name = models.CharField(max_length=100, verbose_name="Имя родителя")
    parent_middle_name = models.CharField(max_length=100, blank=True, verbose_name="Отчество родителя")

    # Данные ребёнка (можно заполнять автоматически из child, но для снэпшота оставить)
    child_last_name = models.CharField(max_length=100, verbose_name="Фамилия ребёнка")
    child_first_name = models.CharField(max_length=100, verbose_name="Имя ребёнка")
    child_middle_name = models.CharField(max_length=100, blank=True, verbose_name="Отчество ребёнка")
    child_birth_date = models.DateField(verbose_name="Дата рождения ребёнка")
    additional_info = models.TextField(blank=True, verbose_name="Дополнительная информация")

    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Стоимость курса', default=0)
    payment_details = models.TextField(blank=True, verbose_name='Реквизиты для оплаты')
    receipt = models.FileField(upload_to='payment_receipts/%Y/%m/%d/', blank=True, null=True, verbose_name='Чек об оплате')
    receipt_uploaded_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата загрузки чека')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="waiting_docs")
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата отправки на проверку")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.child_first_name} {self.child_last_name} – {self.course.name}"



class EnrollmentDocument(models.Model):
    DOCUMENT_TYPES = [
        ("parent_passport", "Паспорт родителя"),
        ("snils", "СНИЛС ребенка"),
        ("child_birth_cert", "Свидетельство о рождении ребёнка/Паспорт ребёнка"),
    ]
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to="enrollment_docs/%Y/%m/%d/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("enrollment", "document_type")
