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
        # Генерируем уникальный ключ новизны прямо в Python
        enrollment.unread_key = f"enrollment-{enrollment.id}-{enrollment.status}"
    
    document_types = EnrollmentDocument.DOCUMENT_TYPES

    # 2. ЗАЧИСЛЕНИЯ В ГРУППЫ
    from teacher.models import GroupMember, Schedule
    from django.utils.timezone import localtime
    
    group_memberships = GroupMember.objects.filter(
        child__parent=user
    ).select_related('group__course', 'child').order_by('-added_at')
    
    for membership in group_memberships:
        membership.sort_date = localtime(membership.added_at)
        membership.notification_type = 'group_join'
        # Ключ новизны для зачислений
        membership.unread_key = f"group_join-{membership.id}"

    # 3. СБОР ОБНОВЛЕНИЙ РАСПИСАНИЯ (УМНАЯ ГРУППИРОВКА)
    parent_group_ids = group_memberships.values_list('group_id', flat=True).distinct()
    three_days_ago = now - timedelta(days=3)
    
    raw_schedules = Schedule.objects.filter(
        group_id__in=parent_group_ids,
        updated_at__gte=three_days_ago
    ).select_related('group__course').order_by('-updated_at')

    grouped_schedule_updates = {}
    for lesson in raw_schedules:
        local_time = localtime(lesson.updated_at)
        # Группируем по ID группы и времени (с точностью до минуты).
        # Сохранение 10 уроков за 1 секунду теперь станет 1 уведомлением!
        time_key = local_time.strftime('%Y%m%d%H%M') 
        group_key = f"{lesson.group_id}_{time_key}"
        
        if group_key not in grouped_schedule_updates:
            lesson.sort_date = local_time
            lesson.notification_type = 'schedule'
            # Железный уникальный ключ (Группа + Точное время сохранения)
            lesson.unread_key = f"schedule-batch-{group_key}"
            grouped_schedule_updates[group_key] = lesson

    schedule_updates = list(grouped_schedule_updates.values())[:10]

    # ОБЪЕДИНЕНИЕ В ЕДИНУЮ ХРОНОЛОГИЧЕСКУЮ ЛЕНТУ
    notifications_feed = list(enrollments) + list(group_memberships) + list(schedule_updates)
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