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
            enrollment.status = 'awaiting_payment'
            enrollment.price = enrollment.course.price
            enrollment.comment = "" # Очищаем старые комментарии, если они были
            enrollment.payment_details = (
                "ООО 'Образовательный中心'\n"
                "ИНН 1234567890\n"
                "КПП 123456789\n"
                "БИК 044525225\n"
                "Счёт 40702810123456789012\n"
                f"Назначение платежа: Оплата курса {enrollment.course.name}"
            )
            messages.success(request, f'Заявка #{enrollment.id} одобрена. Счёт выставлен.')
            
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

# Вот готовый код функции:
@login_required
@user_passes_test(is_accountant)
def finance_analytics(request):
    now = timezone.now()
    
    # Вычисляем временные границы
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_of_quarter = now - timedelta(days=90)
    
    # 1. ОБЩИЕ ПОКАЗАТЕЛИ (ЗА ВСЁ ВРЕМЯ)
    total_paid = Enrollment.objects.filter(status='paid').aggregate(Sum('price'))['price__sum'] or 0
    total_debt = Enrollment.objects.filter(status__in=['awaiting_payment', 'payment_review']).aggregate(Sum('price'))['price__sum'] or 0
    total_rejected = Enrollment.objects.filter(status='rejected').aggregate(Sum('price'))['price__sum'] or 0

    # 2. ПОКАЗАТЕЛИ ЗА ТЕКУЩИЙ МЕСЯЦ
    month_paid = Enrollment.objects.filter(status='paid', updated_at__gte=start_of_month).aggregate(Sum('price'))['price__sum'] or 0
    month_count = Enrollment.objects.filter(status='paid', updated_at__gte=start_of_month).count()
    month_avg = Enrollment.objects.filter(status='paid', updated_at__gte=start_of_month).aggregate(Avg('price'))['price__avg'] or 0

    # 3. ПОКАЗАТЕЛИ ЗА КВАРТАЛ (90 ДНЕЙ)
    quarter_paid = Enrollment.objects.filter(status='paid', updated_at__gte=start_of_quarter).aggregate(Sum('price'))['price__sum'] or 0
    
    # Среднее в месяц за квартал (простая калькуляция)
    avg_monthly_income = quarter_paid / 3

    # 4. СВОДКА ПО КУРСАМ (Выручка по каждому направлению, включая БПЛА)
    course_analytics = Enrollment.objects.filter(status='paid').values(
        'course__name'
    ).annotate(
        total_revenue=Sum('price'),
        students_count=Count('id')
    ).order_by('-total_revenue')

    context = {
        'total_paid': total_paid,
        'total_debt': total_debt,
        'total_rejected': total_rejected,
        'month_paid': month_paid,
        'month_count': month_count,
        'month_avg': month_avg,
        'quarter_paid': quarter_paid,
        'avg_monthly_income': avg_monthly_income,
        'course_analytics': course_analytics,
        'base_template': 'accountant/base_accountant.html',
    }
    return render(request, 'accountant/financial_report.html', context)



from enrollment.models import Enrollment
import os

@login_required
@user_passes_test(is_accountant)
def view_invoice_pdf(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    return render(request, 'accountant/invoice_pdf.html', {
        'enrollment': enrollment,
        'base_template': 'accountant/base_accountant.html'
    })
