from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from enrollment.models import Enrollment
from main.models import Course
from django.contrib import messages

def is_accountant(user):
    return user.groups.filter(name='Бухгалтер').exists()

@login_required
@user_passes_test(is_accountant)
def enrollment_list(request):
   
    # Получаем выбранный статус из GET (если не выбран, показываем только активные)
    selected_status = request.GET.get('status', '')
    if selected_status:
        enrollments = Enrollment.objects.filter(status=selected_status).order_by('-submitted_at')
    else:
        # По умолчанию – требующие внимания: проверка документов и проверка оплаты
        enrollments = Enrollment.objects.filter(status__in=['under_review', 'payment_review']).order_by('-submitted_at')

    # Фильтрация
    parent_name = request.GET.get('parent_name', '')
    course_id = request.GET.get('course', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if parent_name:
        enrollments = enrollments.filter(
            Q(parent_last_name__icontains=parent_name) |
            Q(parent_first_name__icontains=parent_name)
        )
    if course_id:
        enrollments = enrollments.filter(course_id=course_id)
    if date_from:
        enrollments = enrollments.filter(submitted_at__gte=date_from)
    if date_to:
        enrollments = enrollments.filter(submitted_at__lte=date_to)

    # Список курсов для фильтра
    courses = Course.objects.filter(available=True)

    context = {
        'enrollments': enrollments,
        'courses': courses,
        'selected_status': selected_status,
        'filter_parent': parent_name,
        'filter_course': course_id,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
    }
    return render(request, 'accountant/enrollment_list.html', context)


@login_required
@user_passes_test(is_accountant)
def enrollment_detail(request, pk):
    enrollment = get_object_or_404(Enrollment, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        comment = request.POST.get('comment', '')
        if action == 'approve':
            enrollment.status = 'awaiting_payment'
            # Заполняем цену из курса
            enrollment.price = enrollment.course.price
            # Заполняем реквизиты (можно задать статически или из настроек)
            enrollment.payment_details = (
                "ООО 'Образовательный центр'\n"
                "ИНН 1234567890\n"
                "КПП 123456789\n"
                "БИК 044525225\n"
                "Счёт 40702810123456789012\n"
                "Назначение платежа: Оплата курса " + enrollment.course.name
            )
            enrollment.save()
            messages.success(request, f'Заявка #{enrollment.id} одобрена. Теперь родитель может оплатить.')
        elif action == 'reject':
            enrollment.status = 'rejected'
            messages.warning(request, f'Заявка #{enrollment.id} отклонена. Причина: {comment}')
        elif action == 'confirm_payment':
            enrollment.status = 'paid'
            enrollment.save()
            messages.success(request, f'Оплата по заявке #{enrollment.id} подтверждена.')
        elif action == 'reject_payment':
            enrollment.status = 'awaiting_payment'  # или payment_rejected
            enrollment.receipt = None
            enrollment.save()
            messages.warning(request, f'Чек отклонён, заявка возвращена к оплате.')    
        enrollment.save()
        # Здесь можно отправить email пользователю
        return redirect('accountant:enrollment_list')
    return render(request, 'accountant/enrollment_detail.html', {'enrollment': enrollment})