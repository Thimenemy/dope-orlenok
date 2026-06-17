from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Group, GroupMember, Schedule, JournalEntry, StudentCourseReport
from .forms import GroupForm, AddStudentForm, ScheduleForm
from datetime import timedelta, datetime
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
import json
from django.views.decorators.http import require_POST
from chat.models import ChatRoom
from django.urls import reverse
from enrollment.models import Enrollment


def is_teacher(user):
    return user.groups.filter(name="Преподаватель").exists()


@login_required
@user_passes_test(is_teacher)
def group_list(request):
    # Разделяем выборку по твоему полю is_completed
    active_groups = Group.objects.filter(teacher=request.user, is_completed=False).order_by("-created_at")
    finished_groups = Group.objects.filter(teacher=request.user, is_completed=True).order_by("-created_at")
    
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
        
    return render(request, "teacher/group_list.html", {
        "active_groups": active_groups, 
        "finished_groups": finished_groups, 
        "form": form
    })


@login_required
@user_passes_test(is_teacher)
def generate_schedule_group(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)

    if group.is_completed:
        messages.error(request, "Группа завершена. Расписание заблокировано.")
        return redirect("teacher:group_detail", pk=group.pk)

    if request.method == "POST":
        form = ScheduleForm(request.POST)
        if form.is_valid():
            weekdays = form.cleaned_data["weekdays"]
            start_time = form.cleaned_data["start_time"]
            end_time = form.cleaned_data["end_time"]
            topic_text = f"{start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')}"

            group.schedules.all().delete()
            weekday_map = {
                "mon": 0,
                "tue": 1,
                "wed": 2,
                "thu": 3,
                "fri": 4,
                "sat": 5,
                "sun": 6,
            }
            selected = [weekday_map[d] for d in weekdays]
            current = group.start_date
            while current <= group.end_date:
                if current.weekday() in selected:
                    Schedule.objects.create(
                        group=group,
                        date=current,
                        start_time=start_time,
                        end_time=end_time,
                        topic=topic_text,
                        room="",
                    )
                current += timedelta(days=1)
            messages.success(request, "Расписание успешно обновлено.")
        else:
            messages.error(request, "Ошибка в форме.")
    return redirect("teacher:group_detail", pk=group.pk)


@login_required
@user_passes_test(is_teacher)
def group_detail(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)

    if request.method == "POST":
        if group.is_completed:
            messages.error(
                request, "Группа завершена. Редактирование полностью заблокировано."
            )
            return redirect("teacher:group_detail", pk=group.pk)

        if "add_student" in request.POST:
            form = AddStudentForm(request.POST, group=group)
            if form.is_valid():
                child = form.cleaned_data["child"]
                if group.members.count() < group.max_students:
                    GroupMember.objects.get_or_create(group=group, child=child)
                    messages.success(
                        request,
                        f"Ученик {child.last_name} {child.first_name} добавлен в группу.",
                    )
                else:
                    messages.error(request, "Достигнут максимум учеников в группе.")
            else:
                messages.error(request, "Ошибка при добавлении ученика.")
            return redirect("teacher:group_detail", pk=group.pk)

        if "save_journal" in request.POST:
            for key, value in request.POST.items():
                if key.startswith("attendance_"):
                    entry_id = key.split("_")[1]
                    entry = JournalEntry.objects.get(id=entry_id)
                    entry.attendance = value == "true"
                    entry.save()
                elif key.startswith("comment_"):
                    entry_id = key.split("_")[1]
                    entry = JournalEntry.objects.get(id=entry_id)
                    entry.comment = value
                    entry.save()
            messages.success(request, "Журнал сохранён")
            return redirect("teacher:group_detail", pk=group.pk)

    members = group.members.select_related("child").all()
    schedules = group.schedules.order_by("date")
    has_schedule = schedules.exists()
    weekday_names = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]

    weeks_data = {}
    for s in schedules:
        start_of_week = s.date - timedelta(days=s.date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        if start_of_week not in weeks_data:
            weeks_data[start_of_week] = {
                "start": start_of_week,
                "end": end_of_week,
                "days": {i: [] for i in range(7)},
            }
        weeks_data[start_of_week]["days"][s.date.weekday()].append(s)
    weeks_list = sorted(weeks_data.values(), key=lambda w: w["start"])
    for week in weeks_list:
        week["days_dates"] = [(week["start"] + timedelta(days=i)) for i in range(7)]

    journal_rows = []
    if has_schedule:
        for member in members:
            entries_list = []
            for s in schedules:
                entry, _ = JournalEntry.objects.get_or_create(
                    student=member.child, schedule=s
                )
                entries_list.append(entry)
            journal_rows.append({"student": member.child, "entries_list": entries_list})

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
        "group": group,
        "members": members,
        "has_schedule": has_schedule,
        "selected_weekdays": selected_weekdays,
        "start_time": start_time,
        "end_time": end_time,
        "weeks": weeks_list,
        "weekday_names": weekday_names,
        "schedules": schedules,
        "journal_rows": journal_rows,
        "form": AddStudentForm(group=group),
    }
    return render(request, "teacher/group_detail.html", context)


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
                "days": [[] for _ in range(7)],
            }
        weeks_dict[key]["days"][s.date.weekday()].append(s)

    weeks_list = sorted(weeks_dict.values(), key=lambda w: w["start"])
    return render(
        request, "teacher/schedule_view.html", {"group": group, "weeks": weeks_list}
    )


@login_required
@user_passes_test(is_teacher)
@ensure_csrf_cookie
def update_cell(request, group_id, date):
    group = get_object_or_404(Group, pk=group_id, teacher=request.user)
    if group.is_completed:
        return JsonResponse(
            {"status": "error", "message": "Группа завершена"}, status=403
        )

    text = request.POST.get("text", "")
    if text:
        Schedule.objects.update_or_create(
            group=group,
            date=date,
            defaults={"topic": text, "start_time": None, "end_time": None},
        )
    else:
        Schedule.objects.filter(group=group, date=date).delete()
    return JsonResponse({"status": "ok"})


@login_required
@user_passes_test(is_teacher)
@require_POST
def save_all_changes(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)
    if group.is_completed:
        return JsonResponse(
            {"status": "error", "message": "Группа завершена"}, status=403
        )

    try:
        data = json.loads(request.body)
        changes = data.get("changes", [])
        for change in changes:
            date_str = change.get("date")
            text = change.get("text", "").strip()
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            if text:
                Schedule.objects.update_or_create(
                    group=group,
                    date=date_obj,
                    defaults={"topic": text, "start_time": None, "end_time": None},
                )
            else:
                Schedule.objects.filter(group=group, date=date_obj).delete()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)}, status=500)


@login_required
@user_passes_test(is_teacher)
def journal_view(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)
    members = group.members.select_related("child").all()
    schedules = group.schedules.order_by("date")

    for member in members:
        for schedule in schedules:
            JournalEntry.objects.get_or_create(
                student=member.child,
                schedule=schedule,
                defaults={
                    "attendance": False,
                    "comment": "",
                },  # Убрали grade из default
            )

    rows = []
    for member in members:
        row = {
            "student": member.child,
            "entries": {
                schedule.id: JournalEntry.objects.get(
                    student=member.child, schedule=schedule
                )
                for schedule in schedules
            },
        }
        rows.append(row)

    context = {
        "group": group,
        "rows": rows,
        "schedules": schedules,
    }
    return render(request, "teacher/journal.html", context)


@login_required
@user_passes_test(is_teacher)
def create_group_chat_for_group(request, group_id):
    group = get_object_or_404(Group, pk=group_id, teacher=request.user)
    existing = ChatRoom.objects.filter(teacher_group=group).first()
    if existing:
        return redirect("chat:chat_detail", room_id=existing.id)

    members = group.members.select_related("child")
    parents = set(m.child.parent for m in members if m.child.parent)
    if not parents:
        messages.error(request, "Нет родителей для создания чата.")
        return redirect("teacher:group_detail", pk=group.id)

    room = ChatRoom.objects.create(
        room_type="group",
        name=f"Чат группы {group.name}",
        teacher_group=group,
        created_by=request.user,
    )
    room.participants.set(list(parents) + [request.user])
    messages.success(request, f'Чат для группы "{group.name}" создан.')
    return redirect("chat:chat_detail", room_id=room.id)


@login_required
@user_passes_test(is_teacher)
def group_chat_redirect(request, pk):
    group = get_object_or_404(Group, pk=pk, teacher=request.user)
    room = ChatRoom.objects.filter(teacher_group=group).first()

    if room:
        url = reverse("chat:chat_detail", args=[room.id]) + f"?from_group={group.id}"
        return redirect(url)

    members = group.members.select_related("child")
    parents = set()
    for m in members:
        parent = m.child.parent
        if parent:
            parents.add(parent)

    if not parents:
        messages.error(request, "Нет родителей для создания чата.")
        return redirect("teacher:group_detail", pk=group.id)

    room = ChatRoom.objects.create(
        room_type="group",
        name=f"Чат группы {group.name}",
        teacher_group=group,
        created_by=request.user,
    )
    participants = list(parents) + [request.user]
    room.participants.set(participants)

    messages.success(request, f'Чат для группы "{group.name}" создан.')
    url = reverse("chat:chat_detail", args=[room.id]) + f"?from_group={group.id}"
    return redirect(url)


# teacher/views.py


@login_required
@user_passes_test(is_teacher)
def complete_course(request, group_id):
    group = get_object_or_404(Group, id=group_id, teacher=request.user)

    if request.method == "POST":
        for member in group.members.all():
            child = member.child
            entries = JournalEntry.objects.filter(student=child, schedule__group=group)

            total = entries.count()
            attended = entries.filter(attendance=True).count()

            # Высчитываем чистый процент присутствия
            attendance_percent = (attended / total * 100) if total > 0 else 0

            # 🛡️ ЖЕСТКАЯ КОРРЕКТИРОВКА УРОВНЕЙ ПО ТВОЕМУ ТЗ:
            if attendance_percent >= 90:
                level = "Отличный уровень"
            elif attendance_percent >= 75:
                # 75 и выше, но ниже 90
                level = "Хороший уровень"
            elif attendance_percent >= 60:
                # ниже 75, но не ниже 60
                level = "Удовлетворительный уровень"
            else:
                # ниже 60
                level = "Плохой уровень"

            StudentCourseReport.objects.update_or_create(
                group=group,
                student=child,
                defaults={
                    "total_lessons": total,
                    "attended_lessons": attended,
                    "knowledge_level": level,
                },
            )

        # Автоматическое освобождение коммерческих слотов в лагере
        from enrollment.models import Enrollment

        child_ids = group.members.values_list("child_id", flat=True)
        Enrollment.objects.filter(
            course=group.course, child_id__in=child_ids, status="paid"
        ).update(status="completed")

        group.is_completed = True
        group.save()

        messages.success(
            request,
            f'Курс группы "{group.name}" успешно завершён. Итоговые уровни зафиксированы!',
        )
        return redirect("teacher:group_detail", pk=group.id)

    return redirect("teacher:group_detail", pk=group.id)


@login_required
@user_passes_test(is_teacher)
def reports_list(request):
    reports = StudentCourseReport.objects.filter(
        group__teacher=request.user
    ).select_related("group__course", "student")

    groups = (
        Group.objects.filter(teacher=request.user, reports__isnull=False)
        .select_related("course")
        .distinct()
    )

    courses = {g.course for g in groups if g.course}

    student_name = request.GET.get("student_name", "").strip()
    course_id = request.GET.get("course_id")
    group_id = request.GET.get("group_id")
    status = request.GET.get("status")
    sort_by = request.GET.get("sort_by")

    if student_name:
        reports = reports.filter(student__last_name__icontains=student_name)
    if course_id:
        reports = reports.filter(group__course__id=course_id)
    if group_id:
        reports = reports.filter(group_id=group_id)
    if status:
        reports = reports.filter(knowledge_level__icontains=status)

    # Убрали сортировку по score, оставили только по дате отчета
    if sort_by == "date_asc":
        reports = reports.order_by("generated_at")
    else:
        reports = reports.order_by("-generated_at")

    context = {
        "reports": reports,
        "groups": groups,
        "courses": courses,
        "base_template": "teacher/base_teacher.html",
    }
    return render(request, "teacher/reports_list.html", context)
