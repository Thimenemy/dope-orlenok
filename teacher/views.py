from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Group, GroupMember, Schedule, JournalEntry
from .forms import GroupForm, AddStudentForm, ScheduleForm
from datetime import timedelta, datetime
from calendar import monthrange
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse


def is_teacher(user):
    return user.groups.filter(name="Преподаватель").exists()


@login_required
@user_passes_test(is_teacher)
def group_list(request):
    groups = Group.objects.filter(teacher=request.user).order_by("-created_at")
    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.teacher = request.user
            group.save()
            messages.success(request, f'Группа "{group.name}" создана.')
            return redirect("teacher:group_detail", pk=group.pk)
    else:
        form = GroupForm()
    return render(request, "teacher/group_list.html", {"groups": groups, "form": form})


from .models import Group, GroupMember, Schedule
from .forms import ScheduleForm
from datetime import timedelta

@login_required
@user_passes_test(is_teacher)
def generate_schedule_group(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)
    if request.method == 'POST':
        form = ScheduleForm(request.POST)
        if form.is_valid():
            weekdays = form.cleaned_data['weekdays']
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            # Формируем текст для ячейки
            topic_text = f"{start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')}"

            group.schedules.all().delete()
            weekday_map = {'mon':0, 'tue':1, 'wed':2, 'thu':3, 'fri':4, 'sat':5, 'sun':6}
            selected = [weekday_map[d] for d in weekdays]
            current = group.start_date
            while current <= group.end_date:
                if current.weekday() in selected:
                    Schedule.objects.create(
                        group=group,
                        date=current,
                        start_time=start_time,
                        end_time=end_time,
                        topic=topic_text,   # <-- записываем текст
                        room=''
                    )
                current += timedelta(days=1)
            messages.success(request, 'Расписание успешно обновлено.')
        else:
            messages.error(request, 'Ошибка в форме.')
    return redirect('teacher:group_detail', pk=group.pk)


@login_required
@user_passes_test(is_teacher)
def group_detail(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)
    
    # Обработка добавления ученика
    if request.method == 'POST' and 'add_student' in request.POST:
        form = AddStudentForm(request.POST, group=group)
        if form.is_valid():
            child = form.cleaned_data['child']
            if group.members.count() < group.max_students:
                GroupMember.objects.get_or_create(group=group, child=child)
                messages.success(request, f'Ученик {child.last_name} {child.first_name} добавлен в группу.')
            else:
                messages.error(request, 'Достигнут максимум учеников в группе.')
        else:
            messages.error(request, 'Ошибка при добавлении ученика.')
        return redirect('teacher:group_detail', pk=group.pk)

    # Обработка сохранения журнала
    if request.method == 'POST' and 'save_journal' in request.POST:
        for key, value in request.POST.items():
            if key.startswith('grade_'):
                entry_id = key.split('_')[1]
                entry = JournalEntry.objects.get(id=entry_id)
                entry.grade = value
                entry.save()
            elif key.startswith('attendance_'):
                entry_id = key.split('_')[1]
                entry = JournalEntry.objects.get(id=entry_id)
                entry.attendance = (value == 'true')
                entry.save()
            elif key.startswith('comment_'):
                entry_id = key.split('_')[1]
                entry = JournalEntry.objects.get(id=entry_id)
                entry.comment = value
                entry.save()
        messages.success(request, 'Журнал сохранён')
        return redirect('teacher:group_detail', pk=group.pk)

    # Основные данные
    members = group.members.select_related('child').all()
    schedules = group.schedules.order_by('date')
    has_schedule = schedules.exists()
    weekday_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

    # Подготовка для расписания
    weeks_data = {}
    for s in schedules:
        start_of_week = s.date - timedelta(days=s.date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        if start_of_week not in weeks_data:
            weeks_data[start_of_week] = {
                'start': start_of_week,
                'end': end_of_week,
                'days': {i: [] for i in range(7)}
            }
        weeks_data[start_of_week]['days'][s.date.weekday()].append(s)
    weeks_list = sorted(weeks_data.values(), key=lambda w: w['start'])
    for week in weeks_list:
        week['days_dates'] = [(week['start'] + timedelta(days=i)) for i in range(7)]

    # Данные для журнала
    journal_rows = []
    if has_schedule:
        for member in members:
            entries_list = []
            for s in schedules:
                entry, _ = JournalEntry.objects.get_or_create(student=member.child, schedule=s)
                entries_list.append(entry)
            journal_rows.append({
                'student': member.child,
                'entries_list': entries_list
            })
    else:
        journal_rows = []

    # Данные для модала редактирования расписания
    if has_schedule:
        weekdays_set = {s.date.weekday() for s in schedules}
        selected_weekdays = [weekday_names[d] for d in sorted(weekdays_set)]
        first = schedules.first()
        start_time = first.start_time
        end_time = first.end_time
    else:
        selected_weekdays = []
        start_time = end_time = None

    context = {
        'group': group,
        'members': members,
        'has_schedule': has_schedule,
        'selected_weekdays': selected_weekdays,
        'start_time': start_time,
        'end_time': end_time,
        'weeks': weeks_list,
        'weekday_names': weekday_names,
        'schedules': schedules,
        'journal_rows': journal_rows,
        'form': AddStudentForm(group=group),
    }
    return render(request, 'teacher/group_detail.html', context)

@login_required
@user_passes_test(is_teacher)
def schedule_view(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)
    schedules = Schedule.objects.filter(group=group).order_by("date", "start_time")

    weeks_dict = {}
    for s in schedules:
        year, week_num, _ = s.date.isocalendar()
        key = f"{year}-W{week_num:02d}"
        if key not in weeks_dict:
            start = s.date - timedelta(days=s.date.weekday())
            end = start + timedelta(days=6)
            weeks_dict[key] = {
                "start": start,
                "end": end,
                "days": [[] for _ in range(7)]
            }
        weeks_dict[key]["days"][s.date.weekday()].append(s)

    weeks_list = sorted(weeks_dict.values(), key=lambda w: w["start"])
    return render(request, "teacher/schedule_view.html", {"group": group, "weeks": weeks_list})



@login_required
@user_passes_test(is_teacher)
@ensure_csrf_cookie
def update_cell(request, group_id, date):
    group = get_object_or_404(Group, pk=group_id, teacher=request.user)
    text = request.POST.get('text', '')
    if text:
        Schedule.objects.update_or_create(
            group=group, date=date,
            defaults={'topic': text, 'start_time': None, 'end_time': None}
        )
    else:
        Schedule.objects.filter(group=group, date=date).delete()
    return JsonResponse({'status': 'ok'})

import json
from django.views.decorators.http import require_POST

import json
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

@login_required
@user_passes_test(is_teacher)
@require_POST
def save_all_changes(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)
    try:
        data = json.loads(request.body)
        changes = data.get('changes', [])
        for change in changes:
            date_str = change.get('date')
            text = change.get('text', '').strip()
            # Преобразуем строку даты в объект date
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            if text:
                Schedule.objects.update_or_create(
                    group=group,
                    date=date_obj,
                    defaults={'topic': text, 'start_time': None, 'end_time': None}
                )
            else:
                Schedule.objects.filter(group=group, date=date_obj).delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
    
@login_required
@user_passes_test(is_teacher)
def journal_view(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)
    members = group.members.select_related('child').all()
    schedules = group.schedules.order_by('date')

    # Получаем или создаём записи журнала для всех учеников и занятий
    for member in members:
        for schedule in schedules:
            JournalEntry.objects.get_or_create(
                student=member.child,
                schedule=schedule,
                defaults={'grade': '', 'attendance': True, 'comment': ''}
            )

    # Передаём данные в шаблон как матрицу
    rows = []
    for member in members:
        row = {
            'student': member.child,
            'entries': {schedule.id: JournalEntry.objects.get(student=member.child, schedule=schedule) for schedule in schedules}
        }
        rows.append(row)

    context = {
        'group': group,
        'rows': rows,
        'schedules': schedules,
    }
    return render(request, 'teacher/journal.html', context)

from chat.models import ChatRoom

@login_required
@user_passes_test(is_teacher)
def group_chat_redirect(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)
    room = ChatRoom.objects.filter(teacher_group=group).first()
    if room:
        return redirect('chat:chat_detail', room_id=room.id)
    else:
        return render(request, 'teacher/group_chat_create.html', {'group': group})

@login_required
@user_passes_test(is_teacher)
def create_group_chat_for_group(request, group_id):
    group = get_object_or_404(Group, pk=group_id, teacher=request.user)
    existing = ChatRoom.objects.filter(teacher_group=group).first()
    if existing:
        return redirect('chat:chat_detail', room_id=existing.id)

    members = group.members.select_related('child')
    parents = set(m.child.parent for m in members if m.child.parent)
    if not parents:
        messages.error(request, 'Нет родителей для создания чата.')
        return redirect('teacher:group_detail', pk=group.id)

    room = ChatRoom.objects.create(
        room_type='group',
        name=f'Чат группы {group.name}',
        teacher_group=group,
        created_by=request.user
    )
    room.participants.set(list(parents) + [request.user])
    messages.success(request, f'Чат для группы "{group.name}" создан.')
    return redirect('chat:chat_detail', room_id=room.id)

from django.urls import reverse



@login_required
@user_passes_test(is_teacher)
def group_chat_redirect(request, pk):
    # Получаем группу, убеждаемся, что учитель её ведёт
    group = get_object_or_404(Group, pk=pk, teacher=request.user)

    # Пытаемся найти существующий чат, связанный с этой группой
    room = ChatRoom.objects.filter(teacher_group=group).first()

    if room:
        # Чат уже есть – просто переходим в него с параметром from_group
        url = reverse('chat:chat_detail', args=[room.id]) + f'?from_group={group.id}'
        return redirect(url)

    # Чата нет – создаём новый
    # Собираем всех родителей учеников этой группы
    members = group.members.select_related('child')
    parents = set()
    for m in members:
        parent = m.child.parent
        if parent:
            parents.add(parent)

    if not parents:
        messages.error(request, 'Нет родителей для создания чата.')
        return redirect('teacher:group_detail', pk=group.id)

    # Создаём комнату группового чата
    room = ChatRoom.objects.create(
        room_type='group',
        name=f'Чат группы {group.name}',
        teacher_group=group,
        created_by=request.user
    )
    # Добавляем всех родителей и самого преподавателя
    participants = list(parents) + [request.user]
    room.participants.set(participants)

    messages.success(request, f'Чат для группы "{group.name}" создан.')

    # Перенаправляем в новый чат с параметром from_group
    url = reverse('chat:chat_detail', args=[room.id]) + f'?from_group={group.id}'
    return redirect(url)


from django.db.models import Avg
from .models import Group, JournalEntry, StudentCourseReport

from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Group, JournalEntry, StudentCourseReport

@login_required
@user_passes_test(is_teacher)
def complete_course(request, group_id):
    group = get_object_or_404(Group, id=group_id, teacher=request.user)
    
    if request.method == 'POST':
        # Перебираем всех учеников, зачисленных в эту группу
        for member in group.members.all():
            child = member.child
            
            # Собираем все уроки этого ребёнка в данной группе
            entries = JournalEntry.objects.filter(student=child, schedule__group=group)
            
            total = entries.count()
            
            # 1. Считаем посещаемость по твоему реальному полю 'attendance'
            attended = entries.filter(attendance=True).count()
            
            # 2. Безопасный подсчет среднего балла по твоему реальному полю 'grade'
            # Защищает от ошибок, если препод ввел буквы или оставил пустое место
            valid_grades = []
            for entry in entries:
                if entry.grade and str(entry.grade).strip().isdigit():
                    valid_grades.append(float(entry.grade))
                    
            avg_score = sum(valid_grades) / len(valid_grades) if valid_grades else 0
            
            # Автоматически выставляем уровень знаний на основе балла
            if avg_score >= 4.5:
                level = "Отличное освоение (Продвинутый уровень)"
            elif avg_score >= 3.5:
                level = "Хорошее освоение (Базовый уровень)"
            elif avg_score >= 2.5:
                level = "Удовлетворительное освоение"
            else:
                level = "Курс прослушан (Требуется повторение материала)"

            # Записываем слепок успеваемости в базу данных
            StudentCourseReport.objects.update_or_create(
                group=group,
                student=child,
                defaults={
                    'total_lessons': total,
                    'attended_lessons': attended,
                    'average_score': avg_score,
                    'knowledge_level': level,
                }
            )
            
        # Блокируем группу от дальнейших изменений
        group.is_completed = True
        group.save()
        
        messages.success(request, f'Курс группы "{group.name}" успешно завершён. Отчёты отправлены родителям!')
        return redirect('teacher:group_detail', pk=group.id)
    

from django.db.models import Q

@login_required
@user_passes_test(is_teacher)
def reports_list(request):
    from .models import StudentCourseReport, Group
    
    # 1. Базовый запрос: берем все отчёты текущего преподавателя
    reports = StudentCourseReport.objects.filter(
        group__teacher=request.user
    ).select_related('group__course', 'student')
    
    # 2. Собираем уникальные группы и курсы для выпадающих списков фильтра
    groups = Group.objects.filter(
        teacher=request.user, 
        reports__isnull=False
    ).select_related('course').distinct()
    
    # Используем Set (множество) чтобы избежать дублей курсов
    courses = {g.course for g in groups if g.course}

    # 3. Получаем параметры фильтрации из URL (GET-запрос)
    student_name = request.GET.get('student_name', '').strip()
    course_id = request.GET.get('course_id')
    group_id = request.GET.get('group_id')
    status = request.GET.get('status')
    sort_by = request.GET.get('sort_by')

    # 4. Применяем фильтры
    if student_name:
        reports = reports.filter(student__last_name__icontains=student_name)
    if course_id:
        reports = reports.filter(group__course__id=course_id)
    if group_id:
        reports = reports.filter(group_id=group_id)
    if status:
        # Используем icontains, чтобы искать по ключевому слову из статуса
        reports = reports.filter(knowledge_level__icontains=status)

    # 5. Применяем сортировку
    if sort_by == 'score_desc':
        reports = reports.order_by('-average_score')
    elif sort_by == 'score_asc':
        reports = reports.order_by('average_score')
    elif sort_by == 'date_asc':
        reports = reports.order_by('generated_at')
    else:
        # По умолчанию: сначала самые новые
        reports = reports.order_by('-generated_at')

    context = {
        'reports': reports,
        'groups': groups,
        'courses': courses,
        'base_template': 'teacher/base_teacher.html'
    }
    return render(request, 'teacher/reports_list.html', context)