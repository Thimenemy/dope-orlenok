from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .forms import EnrollmentForm
from .models import Enrollment, EnrollmentDocument
from main.models import Course
from accounts.models import Child 
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .forms import EnrollmentFullForm


def is_parent(user):
    return user.groups.filter(name='Родитель').exists()




@login_required
@user_passes_test(is_parent)
def enroll(request, course_id=None, enrollment_id=None):
    course = get_object_or_404(Course, id=course_id, available=True)

    if request.method == "POST":
        form = EnrollmentFullForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            child = form.cleaned_data['child_id']
            additional_info = form.cleaned_data['additional_info']
            consent = form.cleaned_data['consent']
            offline = request.POST.get("offline") == "1"

            if offline:
                status = 'offline_meeting'
                submitted = None
            else:
                if not consent:
                    form.add_error('consent', 'Необходимо дать согласие')
                    return render(request, "enrollment/enroll_form.html", {'form': form, 'course': course, 'base_template': 'home/base_auth.html'})
                status = 'under_review'
                submitted = timezone.now()

            enrollment = Enrollment(
                user=request.user,
                course=course,
                child=child,
                parent_last_name=request.user.last_name,
                parent_first_name=request.user.first_name,
                parent_middle_name=request.user.profile.middle_name,
                child_last_name=child.last_name,
                child_first_name=child.first_name,
                child_middle_name=child.middle_name,
                child_birth_date=child.birth_date,
                additional_info=additional_info,
                status=status,
                submitted_at=submitted,
            )
            enrollment.save()

            if not offline:
                file_fields = {'parent_passport': 'parent_passport', 'child_snils': 'child_snils', 'child_birth_cert': 'child_birth_cert'}
                for doc_type, field_name in file_fields.items():
                    if field_name in request.FILES:
                        EnrollmentDocument.objects.create(
                            enrollment=enrollment,
                            document_type=doc_type,
                            file=request.FILES[field_name]
                        )
                messages.success(request, "Заявка отправлена на проверку.")
            else:
                messages.success(request, "Заявка оформлена как офлайн-визит.")
            return redirect("home:dashboard")
        # Если форма не валидна – ошибки и данные сохранятся в form
        return render(request, "enrollment/enroll_form.html", {'form': form, 'course': course, 'base_template': 'home/base_auth.html'})
    else:
        # GET – пустая форма
        form = EnrollmentFullForm(user=request.user)
        return render(request, "enrollment/enroll_form.html", {'form': form, 'course': course, 'base_template': 'home/base_auth.html'})
    

@login_required
@user_passes_test(is_parent)
def upload_document(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, user=request.user)
    if request.method == "POST":
        consent = request.POST.get("consent") == "on"

        # Список ожидаемых полей с файлами
        file_fields = ["parent_passport", "child_snils", "child_birth_cert"]

        # Обрабатываем каждый файл, если он передан
        for doc_type in file_fields:
            if doc_type in request.FILES:
                file = request.FILES[doc_type]
                EnrollmentDocument.objects.update_or_create(
                    enrollment=enrollment,
                    document_type=doc_type,
                    defaults={"file": file},
                )

        # Проверяем, загружены ли все три документа
        required_docs = set(file_fields)
        uploaded_docs = set(
            enrollment.documents.values_list("document_type", flat=True)
        )
        all_uploaded = required_docs.issubset(uploaded_docs)

        if all_uploaded and consent:
            enrollment.status = 'submitted'        # новый статус
            enrollment.submitted_at = timezone.now()
            enrollment.save()
            messages.success(request, 'Заявка отправлена. Вы можете удалить её в течение 30 минут.')
        elif not all_uploaded:
            messages.warning(request, "Пожалуйста, загрузите все три документа.")
        elif not consent:
            messages.warning(
                request, "Пожалуйста, дайте согласие на обработку персональных данных."
            )
        else:
            messages.info(request, "Загрузите все документы и подтвердите согласие.")

        return redirect("home:dashboard")
    return JsonResponse({"error": "Неверный запрос"}, status=400)


@login_required
@user_passes_test(is_parent)
def rework_enrollment(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, user=request.user)
    if enrollment.status == "submitted":
        # Удаляем все загруженные документы
        enrollment.documents.all().delete()
        # Меняем статус обратно на ожидание документов
        enrollment.status = "waiting_docs"
        enrollment.save()
        messages.warning(
            request,
            "Заявка возвращена на доработку. Пожалуйста, внесите изменения и загрузите документы заново.",
        )
    else:
        messages.error(
            request, "Невозможно вернуть на доработку заявку в текущем статусе."
        )
    return redirect("home:dashboard")


from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


@login_required
@user_passes_test(is_parent)
def delete_enrollment(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, user=request.user)
    # Разрешаем удаление только если заявка в статусе waiting_docs или draft
    if enrollment.status in ["waiting_docs", "draft"]:
        # Удаляем связанные документы (каскадное удаление настроено в модели)
        enrollment.delete()
        messages.success(request, "Заявка успешно удалена.")
    elif enrollment.status == 'submitted':
        if enrollment.submitted_at and (timezone.now() - enrollment.submitted_at) <= timedelta(minutes=30):
            enrollment.delete()
            messages.success(request, 'Заявка удалена.')
        else:
            messages.error(request, 'С момента отправки прошло более 30 минут. Удаление невозможно. Пожалуйста, свяжитесь с поддержкой.')
    else:
        messages.error(request, "Невозможно удалить заявку в текущем статусе.")
    return redirect("home:dashboard")

@login_required
@user_passes_test(is_parent)
def upload_receipt(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, user=request.user)
    if enrollment.status != 'awaiting_payment':
        messages.error(request, 'Оплата по данной заявке не ожидается.')
        return redirect('home:dashboard')
    if request.method == 'POST' and request.FILES.get('receipt'):
        enrollment.receipt = request.FILES['receipt']
        enrollment.receipt_uploaded_at = timezone.now()
        enrollment.status = 'payment_review'
        enrollment.save()
        messages.success(request, 'Чек загружен. После проверки бухгалтер подтвердит оплату.')
    else:
        messages.error(request, 'Файл не выбран.')
    return redirect('home:dashboard')
