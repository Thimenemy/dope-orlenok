from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .forms import EnrollmentForm, EnrollmentFullForm
from .models import Enrollment, EnrollmentDocument
from main.models import Course
from accounts.models import Child 
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

def is_parent(user):
    return user.groups.filter(name='Родитель').exists()

@login_required
@user_passes_test(is_parent)
def enroll(request, course_id=None, enrollment_id=None):
    course = get_object_or_404(Course, id=course_id, available=True)

    # ЖЕСТКАЯ ПРОВЕРКА НАЛИЧИЯ МЕСТ ПЕРЕД ОФОРМЛЕНИЕМ АНКЕТЫ
    if not course.has_free_slots():
        messages.error(request, f"К сожалению, на курсе '{course.name}' закончились свободные места.")
        return redirect("home:dashboard")

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
        return render(request, "enrollment/enroll_form.html", {'form': form, 'course': course, 'base_template': 'home/base_auth.html'})
    else:
        form = EnrollmentFullForm(user=request.user)
        return render(request, "enrollment/enroll_form.html", {'form': form, 'course': course, 'base_template': 'home/base_auth.html'})


# =========================================================================
# НАША НОВАЯ ВЬЮХА: РЕДАКТИРОВАНИЕ ОТКЛОНЕННОЙ ЗАЯВКИ (ДЛЯ РОДИТЕЛЯ)
# =========================================================================
@login_required
@user_passes_test(is_parent)
def edit_enrollment(request, enrollment_id):
    # Ищем именно ЗАЯВКУ текущего пользователя
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, user=request.user)
    course = enrollment.course

    # ЖЕСТКИЙ БЛОК: ЕСЛИ МЕСТ НЕТ, НЕ ДАЕМ РЕДАКТИРОВАТЬ И ВОЗВРАЩАТЬ В ОЧЕРЕДЬ
    # =========================================================================
    if not course.has_free_slots():
        messages.error(request, f"Невозможно доработать заявку. На курсе '{course.name}' закончились свободные места.")
        return redirect("home:dashboard")

    if request.method == "POST":
        # Передаем POST-данные в форму
        form = EnrollmentFullForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            child = form.cleaned_data['child_id']
            
            # Обновляем текстовые данные в слепке заявки
            enrollment.child = child
            enrollment.child_last_name = child.last_name
            enrollment.child_first_name = child.first_name
            enrollment.child_middle_name = child.middle_name
            enrollment.child_birth_date = child.birth_date
            enrollment.additional_info = form.cleaned_data['additional_info']
            
            # Меняем статус обратно на "На проверке" и ОЧИЩАЕМ комментарий отказа
            enrollment.status = 'under_review'
            enrollment.comment = "" 
            enrollment.submitted_at = timezone.now()
            enrollment.save()

            # Обновляем или перезаписываем новые файлы документов, если родитель их прикрепил
            file_fields = ['parent_passport', 'child_snils', 'child_birth_cert']
            for doc_type in file_fields:
                if doc_type in request.FILES:
                    EnrollmentDocument.objects.update_or_create(
                        enrollment=enrollment,
                        document_type=doc_type,
                        defaults={"file": request.FILES[doc_type]},
                    )

            messages.success(request, "Изменения сохранены. Заявка отправлена на повторную проверку.")
            return redirect("home:dashboard")
    else:
        # GET-запрос: подтягиваем в форму старые данные из заявки, чтобы родителю не писать всё заново
        initial_data = {
            'child_id': enrollment.child,
            'additional_info': enrollment.additional_info,
            'consent': True
        }
        form = EnrollmentFullForm(initial=initial_data, user=request.user)

    return render(request, "enrollment/enroll_form.html", {
        'form': form, 
        'course': course, 
        'enrollment': enrollment, # Передаем саму заявку, чтобы внутри формы отобразить прошлый отказ бухгалтера!
        'base_template': 'home/base_auth.html'
    })


@login_required
@user_passes_test(is_parent)
def upload_document(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, user=request.user)
    if request.method == "POST":
        consent = request.POST.get("consent") == "on"
        file_fields = ["parent_passport", "child_snils", "child_birth_cert"]

        for doc_type in file_fields:
            if doc_type in request.FILES:
                file = request.FILES[doc_type]
                EnrollmentDocument.objects.update_or_create(
                    enrollment=enrollment,
                    document_type=doc_type,
                    defaults={"file": file},
                )

        required_docs = set(file_fields)
        uploaded_docs = set(enrollment.documents.values_list("document_type", flat=True))
        all_uploaded = required_docs.issubset(uploaded_docs)

        if all_uploaded and consent:
            enrollment.status = 'submitted'        
            enrollment.submitted_at = timezone.now()
            enrollment.save()
            messages.success(request, 'Заявка отправлена. Вы можете удалить её в течение 30 минут.')
        elif not all_uploaded:
            messages.warning(request, "Пожалуйста, загрузите все три документа.")
        elif not consent:
            messages.warning(request, "Пожалуйста, дайте согласие на обработку персональных данных.")
        else:
            messages.info(request, "Загрузите все документы и подтвердите согласие.")

        return redirect("home:dashboard")
    return JsonResponse({"error": "Неверный запрос"}, status=400)


@login_required
@user_passes_test(is_parent)
def rework_enrollment(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, user=request.user)
    if enrollment.status == "submitted":
        enrollment.documents.all().delete()
        enrollment.status = "waiting_docs"
        enrollment.save()
        messages.warning(request, "Заявка возвращена на доработку. Пожалуйста, внесите изменения и загрузите документы заново.")
    else:
        messages.error(request, "Невозможно вернуть на доработку заявку в текущем статусе.")
    return redirect("home:dashboard")


@login_required
@user_passes_test(is_parent)
def delete_enrollment(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, user=request.user)
    if enrollment.status in ["waiting_docs", "draft"]:
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