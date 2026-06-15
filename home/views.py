from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from enrollment.models import Enrollment, EnrollmentDocument
from teacher.models import JournalEntry
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from teacher.models import Group


def is_parent(user):
    return user.groups.filter(name='Родитель').exists()


@login_required
@user_passes_test(is_parent)
def dashboard(request):
    # Автоматическое обновление статусов старых заявок
    now = timezone.now()
    submitted_enrollments = Enrollment.objects.filter(
        user=request.user,
        status='submitted',
        submitted_at__lte=now - timedelta(minutes=30)
    )
    for enrollment in submitted_enrollments:
        enrollment.status = 'under_review'
        enrollment.save()

    user = request.user
    profile = user.profile
 
    profile_filled = (
        user.first_name and user.last_name and
        profile.birth_date and profile.gender and
        profile.phone and profile.license_accepted and profile.consent_given
    )
    
    children = user.children.all()
    
    # 1. ЗАЯВКИ
    enrollments = Enrollment.objects.filter(user=user).order_by('-created_at')
    for enrollment in enrollments:
        enrollment.uploaded_docs = {doc.document_type: doc for doc in enrollment.documents.all()}
        enrollment.sort_date = enrollment.updated_at if enrollment.updated_at else enrollment.created_at
        enrollment.notification_type = 'enrollment'
        enrollment.unread_key = f"enrollment-{enrollment.id}-{enrollment.status}"
    
    document_types = EnrollmentDocument.DOCUMENT_TYPES

    # 2. ЗАЧИСЛЕНИЯ В ГРУППЫ
    from teacher.models import GroupMember, Schedule, StudentCourseReport
    from django.utils.timezone import localtime
    
    group_memberships = GroupMember.objects.filter(
        child__parent=user
    ).select_related('group__course', 'child').order_by('-added_at')
    
    for membership in group_memberships:
        membership.sort_date = localtime(membership.added_at)
        membership.notification_type = 'group_join'
        membership.unread_key = f"group_join-{membership.id}"

    # 3. СБОР ОБНОВЛЕНИЙ РАСПИСАНИЯ
    parent_group_ids = group_memberships.values_list('group_id', flat=True).distinct()
    three_days_ago = now - timedelta(days=3)
    
    raw_schedules = Schedule.objects.filter(
        group_id__in=parent_group_ids,
        updated_at__gte=three_days_ago
    ).select_related('group__course').order_by('-updated_at')

    grouped_schedule_updates = {}
    for lesson in raw_schedules:
        local_time = localtime(lesson.updated_at)
        time_key = local_time.strftime('%Y%m%d%H%M') 
        group_key = f"{lesson.group_id}_{time_key}"
        
        if group_key not in grouped_schedule_updates:
            lesson.sort_date = local_time
            lesson.notification_type = 'schedule'
            lesson.unread_key = f"schedule-batch-{group_key}"
            grouped_schedule_updates[group_key] = lesson

    schedule_updates = list(grouped_schedule_updates.values())[:10]

    # --- НАШЕ НОВОЕ РЕШЕНИЕ БЕЗ LOG-ТАБЛИЦ: СОБИРАЕМ ОТЧЁТЫ ОБ УСПЕВАЕМОСТИ ---
    child_ids = children.values_list('id', flat=True)
    course_reports = StudentCourseReport.objects.filter(
        student_id__in=child_ids
    ).select_related('group__course', 'student').order_by('-generated_at')

    for report in course_reports:
        report.sort_date = localtime(report.generated_at)
        report.notification_type = 'course_report'
        # Железный ключ новизны для локалстораджа фронтенда
        report.unread_key = f"course_report-{report.id}"

    # ОБЪЕДИНЕНИЕ В ЕДИНУЮ ХРОНОЛОГИЧЕСКУЮ ЛЕНТУ (Включая отчеты)
    notifications_feed = list(enrollments) + list(group_memberships) + list(schedule_updates) + list(course_reports)
    notifications_feed.sort(key=lambda x: getattr(x, 'sort_date', now), reverse=True)

    context = {
        'profile_filled': profile_filled,
        'children': children,
        'document_types': document_types,
        'notifications_feed': notifications_feed,
        'base_template': 'home/base_auth.html',
    }
    return render(request, 'home/dashboard.html', context)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test


def is_parent(user):
    return user.groups.filter(name='Родитель').exists()

@login_required
@user_passes_test(is_parent)
def parent_schedule(request):
    # Получаем группы, в которых есть хотя бы один ребёнок родителя
    groups = Group.objects.filter(
        members__child__parent=request.user
    ).distinct().prefetch_related('members__child')
    
    # Для каждой группы добавим атрибут parent_children – список детей родителя в этой группе
    for group in groups:
        group.parent_children = group.members.filter(
            child__parent=request.user
        ).select_related('child')
    
    return render(request, 'home/parent_schedule.html', {'groups': groups})

@login_required
@user_passes_test(is_parent)
def get_group_schedule(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    # Проверяем, что у родителя есть доступ к группе (через его детей)
    if not group.members.filter(child__parent=request.user).exists():
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    
    schedules = group.schedules.order_by('date')
    if not schedules.exists():
        return JsonResponse({'html': '<div class="alert alert-info">Расписание не задано</div>'})
    
    # Готовим данные для таблицы (аналогично teacher/views.py group_detail)
    weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    weeks_data = {}
    for s in schedules:
        start_of_week = s.date - timedelta(days=s.date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        key = start_of_week.isoformat()
        if key not in weeks_data:
            weeks_data[key] = {
                'start': start_of_week,
                'end': end_of_week,
                'days': {i: [] for i in range(7)}
            }
        weeks_data[key]['days'][s.date.weekday()].append(s)
    weeks = sorted(weeks_data.values(), key=lambda w: w['start'])
    
    # Рендерим шаблон таблицы (переиспользуем тот же, что у учителя, но без редактирования)
    from django.template.loader import render_to_string
    html = render_to_string('home/_schedule_table.html', {
        'weeks': weeks,
        'weekday_names': weekday_names,
    })
    return JsonResponse({'html': html})

@login_required
@user_passes_test(is_parent)
def group_schedule_page(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    # Проверяем, что у родителя есть доступ (хотя бы один ребёнок в группе)
    if not group.members.filter(child__parent=request.user).exists():
        # Можно вернуть страницу с ошибкой или redirect
        return render(request, 'home/access_denied.html', {'group': group})
    
    schedules = group.schedules.order_by('date')
    if not schedules.exists():
        return render(request, 'home/no_schedule.html', {'group': group})
    
    # Готовим данные для таблицы (как у преподавателя)
    weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    weeks_data = {}
    for s in schedules:
        start_of_week = s.date - timedelta(days=s.date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        key = start_of_week.isoformat()
        if key not in weeks_data:
            weeks_data[key] = {
                'start': start_of_week,
                'end': end_of_week,
                'days': {i: [] for i in range(7)}
            }
        weeks_data[key]['days'][s.date.weekday()].append(s)
    weeks = sorted(weeks_data.values(), key=lambda w: w['start'])
    
    context = {
        'group': group,
        'weeks': weeks,
        'weekday_names': weekday_names,
    }
    return render(request, 'home/schedule_page.html', context)

@login_required
@user_passes_test(is_parent)
def parent_journal(request):
    # Список детей текущего родителя
    children = request.user.children.all()
    selected_child_id = request.GET.get('child_id')
    selected_child = None
    journal_entries = []

    if selected_child_id:
        selected_child = get_object_or_404(children, id=selected_child_id)
        # Получаем все записи журнала для выбранного ребенка, сортируем по дате занятия
        journal_entries = JournalEntry.objects.filter(
            student=selected_child
        ).select_related('schedule__group', 'schedule').order_by('schedule__date')

    context = {
        'children': children,
        'selected_child': selected_child,
        'journal_entries': journal_entries,
    }
    return render(request, 'home/parent_journal.html', context)


@login_required
def view_report_print(request, report_id):
    from teacher.models import StudentCourseReport
    report = get_object_or_404(StudentCourseReport, id=report_id)
    
    # Проверка безопасности: смотреть отчёт может препод или только родитель этого ребёнка
    is_teacher = request.user.groups.filter(name='Преподаватель').exists()
    if not is_teacher and report.student.parent != request.user:
        return render(request, 'home/access_denied.html') # Страница ошибки доступа
        
    return render(request, 'home/report_print_page.html', {
        'report': report,
        'base_template': 'teacher/base_teacher.html' if is_teacher else 'home/base_auth.html'
    })

@login_required
def view_report_print(request, report_id):
    from teacher.models import StudentCourseReport, JournalEntry
    report = get_object_or_404(StudentCourseReport, id=report_id)
    
    # Проверка прав доступа
    is_teacher = request.user.groups.filter(name='Преподаватель').exists()
    if not is_teacher and report.student.parent != request.user:
        return render(request, 'home/access_denied.html')
        
    # --- НАШЕ ДОПОЛНЕНИЕ: ВЫТАСКИВАЕМ ИСТОРИЮ ПОСЕЩЕНИЙ И ОЦЕНОК ---
    lessons_history = JournalEntry.objects.filter(
        student=report.student,
        schedule__group=report.group
    ).select_related('schedule').order_by('schedule__date')
        
    return render(request, 'home/report_print_page.html', {
        'report': report,
        'lessons_history': lessons_history, # Передаём историю уроков в шаблон
        'base_template': 'teacher/base_teacher.html' if is_teacher else 'home/base_auth.html'
    })