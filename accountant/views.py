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
    # Получаем выбранный статус из GET
    selected_status = request.GET.get('status', '')
    if selected_status:
        enrollments = Enrollment.objects.filter(status=selected_status).order_by('-submitted_at')
    else:
        # По умолчанию – требующие внимания: проверка документов и проверка оплаты
        enrollments = Enrollment.objects.filter(status__in=['under_review', 'payment_review']).order_by('-submitted_at')

    # Фильтрация параметров
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

    # Добавляем base_template, чтобы шаблон наследовал правильный сайдбар
    context = {
        'enrollments': enrollments,
        'courses': courses,
        'selected_status': selected_status,
        'filter_parent': parent_name,
        'filter_course': course_id,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
        'base_template': 'accountant/base_accountant.html',
    }
    return render(request, 'accountant/enrollment_list.html', context)


@login_required
@user_passes_test(is_accountant)
def enrollment_detail(request, pk):
    enrollment = get_object_or_404(Enrollment, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        comment_text = request.POST.get('comment', '').strip()
        
        if action == 'approve':
            # 1. Проверяем перед выдачей квитанции, не занял ли кто-то последнее место секунду назад
            if not enrollment.course.has_free_slots():
                messages.error(request, "Невозможно одобрить заявку. Свободные места на курсе закончились!")
                return redirect('accountant:enrollment_list')

            # 2. Переводим заявку в статус резерва. Для твоей ИС это 'awaiting_payment' (Ожидает оплаты)
            enrollment.status = 'awaiting_payment'
            enrollment.price = enrollment.course.price
            enrollment.comment = ""
            enrollment.payment_details = (
                "МУ ОЦ 'Орлёнок'\n"
                "ИНН 1234567890 КПП 123456789\n"
                f"Назначение платежа: Оплата за доп. образование, курс {enrollment.course.name}"
            )
            enrollment.save() # Сохраняем бронь в базу!
            messages.success(request, f'Заявка #{enrollment.id} одобрена. Счёт выставлен родителям.')

            # 3. АВТОМАТИЧЕСКАЯ ОТМЕНА ОСТАЛЬНЫХ, ЕСЛИ МЕСТА КОНЧИЛИСЬ
            current_course = enrollment.course
            if not current_course.has_free_slots():
                # Находим всех, кто подал доки на этот же курс и до сих пор висит в очереди на проверку
                waiting_others = Enrollment.objects.filter(
                    course=current_course,
                    status='under_review'
                ).exclude(id=enrollment.id)
                
                # Считаем точное число людей, которые сейчас держат квитанции (резерв)
                reserve_count = current_course.get_reserve_slots_count()

                # Построчно отменяем их заявки с твоим кастомным текстом
                for other_enrollment in waiting_others:
                    other_enrollment.status = 'rejected'
                    other_enrollment.comment = (
                        "Автоматический отказ системы: К сожалению, свободные места на выбранный курс закончились. "
                        f"Попробуйте зайти через 3 дня, сейчас в резерве находится мест: {reserve_count}. "
                        "Если кто-то из заявителей не оплатит выставленный счёт вовремя, места будут освобождены."
                    )
                    other_enrollment.save()
                
                messages.warning(request, f"На курсе {current_course.name} закончились места. Остальные заявки в очереди ({waiting_others.count()} шт.) автоматически отклонены.")
            
        elif action == 'reject':
            enrollment.status = 'rejected'
            enrollment.comment = comment_text # ЖЕСТКО ЗАПИСЫВАЕМ ПРИЧИНУ В БАЗУ ДАННЫХ
            messages.warning(request, f'Заявка #{enrollment.id} отклонена. Причина: {comment_text}')
            
        elif action == 'confirm_payment':
            enrollment.status = 'paid'
            enrollment.comment = "" # Очищаем комментарии при успешной проводке
            messages.success(request, f'Оплата по заявке #{enrollment.id} подтверждена. Ребенок зачислен.')
            
        elif action == 'reject_payment':
            # При отклонении чека переводим обратно в rejected, чтобы родитель видел ошибку в ленте
            enrollment.status = 'rejected' 
            enrollment.comment = comment_text # ЖЕСТКО ЗАПИСЫВАЕМ ПРИЧИНУ ОТКЛОНЕНИЯ ЧЕКА
            
            # Удаляем плохой чек, чтобы родитель мог загрузить новый
            if enrollment.receipt:
                enrollment.receipt.delete(save=False)
            enrollment.receipt = None
            messages.warning(request, f'Чек по заявке #{enrollment.id} отклонён. Причина: {comment_text}')    
        
        # Финальное сохранение объекта со всеми новыми данными
        enrollment.save()
        return redirect('accountant:enrollment_list')
        
    return render(request, 'accountant/enrollment_detail.html', {
        'enrollment': enrollment,
        'base_template': 'accountant/base_accountant.html'
    })


from django.db.models import Sum, Avg, Count
from django.utils import timezone
from datetime import timedelta
from enrollment.models import Enrollment

@login_required
@user_passes_test(is_accountant)
def financial_report(request):  # или name finance_analytics, главное чтоб совпадало с urls.py
    pass

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum
from enrollment.models import Enrollment
from main.models import Course

def is_accountant(user):
    return user.groups.filter(name='Бухгалтер').exists()

@login_required
@user_passes_test(is_accountant)
def finance_analytics(request):
    # 1. Получаем параметры фильтрации из GET
    financial_type = request.GET.get('financial_type', '') # прибыль, задолженность, удержание
    course_id = request.GET.get('course', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    # Базовый кверисет (берем только те заявки, которые прошли верификацию документов)
    enrollments = Enrollment.objects.exclude(status__in=['draft', 'waiting_docs', 'under_review', 'submitted'])

    # 2. Фильтрация по типу финансового показателя
    if financial_type == 'profit':
        enrollments = enrollments.filter(status='paid')
    elif financial_type == 'debt':
        enrollments = enrollments.filter(status__in=['awaiting_payment', 'payment_review'])
    elif financial_type == 'rejected':
        enrollments = enrollments.filter(status='rejected')

    # 3. Фильтрация по курсу
    if course_id:
        enrollments = enrollments.filter(course_id=course_id)

    # 4. Фильтрация по периоду (смотрим на дату изменения операции updated_at)
    if date_from:
        enrollments = enrollments.filter(updated_at__date__gte=date_from)
    if date_to:
        enrollments = enrollments.filter(updated_at__date__lte=date_to)

    # Сортируем по дате операции (сначала новые)
    enrollments = enrollments.order_by('-updated_at')

    # 5. Вычисляем строку ИТОГО по отфильтрованному результату
    total_sum = enrollments.aggregate(Sum('price'))['price__sum'] or 0

    # Список курсов для выпадающего меню
    courses = Course.objects.filter(available=True)

    context = {
        'enrollments': enrollments,
        'courses': courses,
        'total_sum': total_sum,
        'selected_financial_type': financial_type,
        'filter_course': course_id,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
        'base_template': 'accountant/base_accountant.html',
    }
    return render(request, 'accountant/financial_report.html', context)



from enrollment.models import Enrollment

@login_required
@user_passes_test(is_accountant)
def view_invoice_pdf(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    return render(request, 'accountant/invoice_pdf.html', {
        'enrollment': enrollment,
        'base_template': 'accountant/base_accountant.html'
    })
