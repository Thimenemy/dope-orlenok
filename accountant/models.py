from django.db import models
from enrollment.models import Enrollment

# Create your models here.
class Invoice(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="invoices")
    pdf_file = models.FileField(upload_to='invoices/%Y/%m/%d/', verbose_name="Файл счёта (PDF)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Счёт для {self.enrollment.id}"