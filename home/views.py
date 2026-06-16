from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from enrollment.models import Enrollment, EnrollmentDocument
from teacher.models import JournalEntry, Group, GroupMember, Schedule, StudentCourseReport
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.utils.timezone import localtime
from django.views.decorators.http import require_POST
import json
from accounts.models import Child

def is_parent(user):
    return user.groups.filter(name='Родитель').exists()

@login_required
def dashboard(request):
    user = request.user

    # ИЗОЛЯЦИЯ РЕБЕНКА: ЕСЛИ ЭТО РЕБЕНОК, СРАЗУ ОТДАЕМ ЕГО ШАБЛОН И ВЫХОДИМ!
    if user.groups.filter(name='Ребёнок').exists():
        child_profile = Child.objects.filter(user=user).first()
        my_groups = []
        if child_profile:
            my_groups = GroupMember.objects.filter(child=child_profile).select_related('group__course')

        return render(request, 'home/dashboard_child.html', {
            'child': child_profile,
            'my_groups': my_groups,
            'base_template': 'home/base_child.html'
        })

    # ЕСЛИ ЭТО РАБОТНИКИ ЛАГЕРЯ, ОТПРАВЛЯЕМ ИХ В СВОИ КАБИНЕТЫ
    if user.is_staff and user.is_superuser:
        return redirect("dashboard_admin:course_list")
    if user.groups.filter(name="Бухгалтер").exists():
        return redirect("accountant:enrollment_list")
    if user.groups.filter(name="Преподаватель").exists():
        return redirect("teacher:group_list")

    # ЕСЛИ ЮЗЕР НЕ РОДИТЕЛЬ
    if not is_parent(user):
        return render(request, 'home/access_denied.html')

    # ЛОГИКА ДЛЯ РОДИТЕЛЯ
    now = timezone.now()
    submitted_enrollments = Enrollment.objects.filter(
        user=request.user, status='submitted', submitted_at__lte=now - timedelta(minutes=30)
    )
    for enrollment in submitted_enrollments:
        enrollment.status = 'under_review'
        enrollment.save()

    profile = user.profile
    profile_filled = (
        user.first_name and user.last_name and profile.birth_date and profile.gender and
        profile.phone and profile.license_accepted and profile.consent_given
    )
    
    children = user.children.all()
    enrollments = Enrollment.objects.filter(user=user).order_by('-created_at')
    for enrollment in enrollments:
        enrollment.uploaded_docs = {doc.document_type: doc for doc in enrollment.documents.all()}
        enrollment.sort_date = enrollment.updated_at if enrollment.updated_at else enrollment.created_at
        enrollment.notification_type = 'enrollment'
        enrollment.unread_key = f"enrollment-{enrollment.id}-{enrollment.status}"
    
    document_types = EnrollmentDocument.DOCUMENT_TYPES
    group_memberships = GroupMember.objects.filter(child__parent=user).select_related('group__course', 'child').order_by('-added_at')
    
    for membership in group_memberships:
        membership.sort_date = localtime(membership.added_at)
        membership.notification_type = 'group_join'
        membership.unread_key = f"group_join-{membership.id}"

    parent_group_ids = group_memberships.values_list('group_id', flat=True).distinct()
    three_days_ago = now - timedelta(days=3)
    
    raw_schedules = Schedule.objects.filter(group_id__in=parent_group_ids, updated_at__gte=three_days_ago).select_related('group__course').order_by('-updated_at')

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
    child_ids = children.values_list('id', flat=True)
    course_reports = StudentCourseReport.objects.filter(student_id__in=child_ids).select_related('group__course', 'student').order_by('-generated_at')

    for report in course_reports:
        report.sort_date = localtime(report.generated_at)
        report.notification_type = 'course_report'
        report.unread_key = f"course_report-{report.id}"

    notifications_feed = list(enrollments) + list(group_memberships) + list(schedule_updates) + list(course_reports)
    notifications_feed.sort(key=lambda x: getattr(x, 'sort_date', now), reverse=True)
    
    read_keys = [k.strip() for k in profile.read_notifications_data.split(',') if k.strip()]
    for item in notifications_feed:
        item.is_unread_by_db = item.unread_key not in read_keys

    return render(request, 'home/dashboard.html', {
        'profile_filled': profile_filled, 'children': children, 'document_types': document_types,
        'notifications_feed': notifications_feed, 'base_template': 'home/base_auth.html'
    })

@login_required
@require_POST
def mark_notification_read_ajax(request):
    try:
        data = json.loads(request.body)
        unread_id = data.get('unread_id', '').strip()
        if unread_id:
            profile = request.user.profile
            current_keys = [k.strip() for k in profile.read_notifications_data.split(',') if k.strip()]
            if unread_id not in current_keys:
                current_keys.append(unread_id)
                profile.read_notifications_data = ",".join(current_keys)
                profile.save()
                return JsonResponse({'status': 'ok'})
            return JsonResponse({'status': 'already_read'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid ID'}, status=400)

@login_required
def parent_schedule(request):
    groups = Group.objects.filter(members__child__parent=request.user).distinct().prefetch_related('members__child')
    for group in groups:
        group.parent_children = group.members.filter(child__parent=request.user).select_related('child')
    return render(request, 'home/parent_schedule.html', {'groups': groups})

@login_required
def get_group_schedule(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    schedules = group.schedules.order_by('date')
    if not schedules.exists():
        return JsonResponse({'html': '<div class="alert alert-info">Расписание не задано</div>'})
    weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    weeks_data = {}
    for s in schedules:
        start_of_week = s.date - timedelta(days=s.date.weekday())
        key = start_of_week.isoformat()
        if key not in weeks_data:
            weeks_data[key] = {'start': start_of_week, 'days': {i: [] for i in range(7)}}
        weeks_data[key]['days'][s.date.weekday()].append(s)
    weeks = sorted(weeks_data.values(), key=lambda w: w['start'])
    from django.template.loader import render_to_string
    html = render_to_string('home/_schedule_table.html', {'weeks': weeks, 'weekday_names': weekday_names})
    return JsonResponse({'html': html})

@login_required
def group_schedule_page(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    schedules = group.schedules.order_by('date')
    weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    weeks_data = {}
    for s in schedules:
        start_of_week = s.date - timedelta(days=s.date.weekday())
        key = start_of_week.isoformat()
        if key not in weeks_data:
            weeks_data[key] = {'start': start_of_week, 'days': {i: [] for i in range(7)}}
        weeks_data[key]['days'][s.date.weekday()].append(s)
    weeks = sorted(weeks_data.values(), key=lambda w: w['start'])
    return render(request, 'home/schedule_page.html', {'group': group, 'weeks': weeks, 'weekday_names': weekday_names})

@login_required
def parent_journal(request):
    children = request.user.children.all()
    selected_child_id = request.GET.get('child_id')
    selected_child = None
    journal_entries = []
    if selected_child_id:
        selected_child = get_object_or_404(children, id=selected_child_id)
        journal_entries = JournalEntry.objects.filter(student=selected_child).select_related('schedule__group', 'schedule').order_by('schedule__date')
    return render(request, 'home/parent_journal.html', {'children': children, 'selected_child': selected_child, 'journal_entries': journal_entries})

@login_required
def view_report_print(request, report_id):
    report = get_object_or_404(StudentCourseReport, id=report_id)
    lessons_history = JournalEntry.objects.filter(student=report.student, schedule__group=report.group).select_related('schedule').order_by('schedule__date')
    return render(request, 'home/report_print_page.html', {'report': report, 'lessons_history': lessons_history, 'base_template': 'home/base_auth.html'})