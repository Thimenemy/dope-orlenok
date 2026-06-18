from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from .models import ChatRoom, ChatMessage
from .forms import CreateChatForm
from teacher.models import Group
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import Count, Q

User = get_user_model()


def is_teacher(user):
    return user.groups.filter(name="Преподаватель").exists()


def is_parent(user):
    return user.groups.filter(name="Родитель").exists()


def get_base_template(user):
    if user.groups.filter(name="Преподаватель").exists():
        return "teacher/base_teacher.html"
    return "home/base_auth.html"


@login_required
def chat_list(request):
    # 1. Получаем список комнат БЕЗ глючного annotate
    rooms = request.user.chat_rooms.exclude(deleted_for=request.user).order_by(
        "-updated_at"
    )

    rooms_data = []
    for room in rooms:
        if room.room_type == "group":
            display_name = room.name or "Групповой чат"
        else:
            other = room.participants.exclude(id=request.user.id).first()
            if other:
                display_name = (
                    f"{other.last_name} {other.first_name}".strip() or other.username
                )
            else:
                display_name = "Неизвестный участник"

        # 2. ЖЕЛЕЗОБЕТОННЫЙ ПОДСЧЕТ: Ищем конкретно в этой комнате чужие сообщения,
        # которых физически нет в нашем списке прочитанного.
        unread_count = (
            room.messages.exclude(sender=request.user)
            .exclude(read_by=request.user)
            .count()
        )

        rooms_data.append(
            {"room": room, "display_name": display_name, "unread_count": unread_count}
        )

    is_teacher_user = request.user.groups.filter(name="Преподаватель").exists()
    base_template = get_base_template(request.user)

    hidden_rooms = []
    if is_teacher_user:
        hidden_rooms = (
            ChatRoom.objects.filter(deleted_for__isnull=False)
            .exclude(deleted_for=request.user)
            .distinct()
        )

    return render(
        request,
        "chat/chat_list.html",
        {
            "rooms_data": rooms_data,
            "is_teacher": is_teacher_user,
            "is_parent": not is_teacher_user,
            "base_template": base_template,
            "hidden_rooms": hidden_rooms,
        },
    )


@login_required
def chat_detail(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in room.participants.all():
        messages.error(request, "Нет доступа")
        return redirect("chat:chat_list")

    # Сброс уведомлений
    unread_messages = room.messages.exclude(sender=request.user).exclude(
        read_by=request.user
    )
    if unread_messages.exists():
        for msg in unread_messages:
            msg.read_by.add(request.user)

    messages_history = room.messages.all()

    # --- ЖЕЛЕЗНАЯ ЛОГИКА РАЗВОДКИ ШАБЛОНОВ ---
    user = request.user
    is_admin = user.is_staff or user.is_superuser
    is_teacher = user.groups.filter(name="Преподаватель").exists()
    is_child = user.groups.filter(name="Ребёнок").exists()

    # Маркер прихода из админки
    from_admin = request.GET.get("from_admin")

    if is_admin or from_admin:
        base_template = "dashboard_admin/base_admin.html"
        back_url = reverse("dashboard_admin:chat_list")
    elif is_teacher:
        base_template = "teacher/base_teacher.html"
        back_url = reverse("chat:chat_list")  # Стандарт для учителя
    elif is_child:
        base_template = "home/base_child.html"  # Твой новый шаблон для ребенка
        back_url = reverse("home:dashboard")
    else:
        base_template = "home/base_auth.html"  # Родитель
        back_url = reverse("chat:chat_list")

    # Если препод пришел из группы - переопределяем back_url
    from_group = request.GET.get("from_group")
    if from_group and is_teacher:
        try:
            group_id = int(from_group)
            if user.teaching_groups.filter(id=group_id).exists():
                back_url = (
                    reverse("teacher:group_detail", args=[group_id]) + "#chats-tab"
                )
        except ValueError:
            pass
    # ----------------------------------------

    other_participant = None
    if room.room_type == "private":
        other_participant = room.participants.exclude(id=user.id).first()

    available_users = []
    if room.room_type == "group" and (room.created_by == user or is_teacher):
        from teacher.models import GroupMember
        from accounts.models import Child
        
        # Если чат привязан к конкретной учебной группе
        if room.teacher_group_id:
            # 1. Получаем ID детей этой группы
            child_ids = GroupMember.objects.filter(
                group_id=room.teacher_group_id
            ).values_list('child_id', flat=True)
            
            # 2. Получаем родителей этих детей и исключаем тех, кто уже в чате
            available_users = User.objects.filter(
                children__id__in=child_ids
            ).exclude(
                id__in=room.participants.values_list('id', flat=True)
            ).distinct()
        else:
            # Стандартная логика, если чат не привязан к группе (например, админский)
            available_users = User.objects.exclude(
                id__in=room.participants.values_list('id', flat=True)
            ).exclude(id=user.id)

    chat_is_disabled = False
    if room.teacher_group_id and room.teacher_group.is_completed:
        chat_is_disabled = True

    context = {
        "room": room,
        "messages": messages_history,
        "base_template": base_template,
        "back_url": back_url,
        "is_teacher": is_teacher,
        "other_participant": other_participant,
        "available_users": available_users,
        'chat_is_disabled': chat_is_disabled,
    }
    return render(request, "chat/chat_detail.html", context)


@login_required
def create_chat(request):
    if request.method == "POST":
        form = CreateChatForm(request.POST, user=request.user)
        if form.is_valid():
            chat_type = form.cleaned_data["chat_type"]
            name = form.cleaned_data.get("name")
            participants = list(form.cleaned_data["participants"])
            if chat_type == "private":
                other = participants[0] if participants else None
                if other:
                    existing = (
                        ChatRoom.objects.filter(
                            room_type="private", participants=request.user
                        )
                        .filter(participants=other)
                        .distinct()
                        .first()
                    )
                    if existing:
                        return redirect("chat:chat_detail", room_id=existing.id)
                room = ChatRoom.objects.create(
                    room_type="private", created_by=request.user
                )
                room.participants.add(request.user, other)
                return redirect("chat:chat_detail", room_id=room.id)
            elif chat_type == "group":
                if not name:
                    form.add_error("name", "Укажите название группового чата")
                else:
                    existing = ChatRoom.objects.filter(
                        room_type="group", name=name, participants=request.user
                    ).first()
                    if existing:
                        return redirect("chat:chat_detail", room_id=existing.id)
                    room = ChatRoom.objects.create(
                        room_type="group", name=name, created_by=request.user
                    )
                    room.participants.set(participants + [request.user])
                    return redirect("chat:chat_detail", room_id=room.id)
    else:
        form = CreateChatForm(user=request.user)
    base_template = get_base_template(request.user)
    return render(
        request, "chat/create_chat.html", {"form": form, "base_template": base_template}
    )


@login_required
def create_private_chat(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    existing = (
        ChatRoom.objects.filter(room_type="private", participants=request.user)
        .filter(participants=other_user)
        .distinct()
        .first()
    )
    if existing:
        if existing.deleted_for.filter(id=request.user.id).exists():
            existing.deleted_for.remove(request.user)
        return redirect("chat:chat_detail", room_id=existing.id)
    room = ChatRoom.objects.create(room_type="private", created_by=request.user)
    room.participants.add(request.user, other_user)
    return redirect("chat:chat_detail", room_id=room.id)


@login_required
def delete_chat_for_me(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in room.participants.all():
        messages.error(request, "Нет доступа")
        return redirect("chat:chat_list")
    room.deleted_for.add(request.user)
    messages.success(request, "Чат скрыт из вашего списка")
    return redirect("chat:chat_list")


@login_required
@user_passes_test(is_teacher)
def delete_chat_permanently(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in room.participants.all():
        messages.error(request, "Нет доступа")
        return redirect("chat:chat_list")
    room.delete()
    messages.success(request, "Чат удалён полностью")
    return redirect("chat:chat_list")


@login_required
@user_passes_test(is_teacher)
def restore_for_user(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    room.deleted_for.clear()
    messages.success(request, "Чат восстановлен для всех участников.")
    return redirect("chat:chat_list")


@login_required
def invite_to_group_chat(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    is_teacher_user = request.user.groups.filter(name="Преподаватель").exists()
    
    if room.room_type != "group" or (room.created_by != request.user and not is_teacher_user):
        messages.error(request, "У вас нет прав для управления участниками этого чата.")
        return redirect("chat:chat_detail", room_id=room.id)
        
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        new_user = get_object_or_404(User, id=user_id)
        
        # ЗАЩИТА: Проверяем, имеет ли право препод добавлять этого юзера
        if is_teacher_user and room.teacher_group_id:
            from teacher.models import GroupMember
            # Допустимые родители для этой группы
            valid_parent_ids = User.objects.filter(
                children__id__in=GroupMember.objects.filter(
                    group_id=room.teacher_group_id
                ).values_list('child_id', flat=True)
            ).values_list('id', flat=True)
            
            if new_user.id not in valid_parent_ids and not new_user.is_staff:
                messages.error(request, "Ошибка безопасности: Пользователь не относится к этой группе.")
                return redirect("chat:chat_detail", room_id=room.id)

        if new_user in room.participants.all():
            messages.warning(request, "Пользователь уже в чате.")
        else:
            room.participants.add(new_user)
            room.deleted_for.remove(new_user)
            messages.success(request, f"{new_user.get_full_name()} добавлен в чат.")
            
    return redirect("chat:chat_detail", room_id=room.id)


@login_required
def remove_from_group_chat(request, room_id, user_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    is_teacher_user = request.user.groups.filter(name="Преподаватель").exists()
    if room.room_type != "group" or (
        room.created_by != request.user and not is_teacher_user
    ):
        messages.error(request, "У вас нет прав для управления участниками этого чата.")
        return redirect("chat:chat_detail", room_id=room.id)
    user_to_remove = get_object_or_404(User, id=user_id)
    if user_to_remove == room.created_by:
        messages.error(request, "Нельзя исключить создателя чата.")
        return redirect("chat:chat_detail", room_id=room.id)
    room.participants.remove(user_to_remove)
    room.deleted_for.remove(user_to_remove)
    messages.success(request, f"{user_to_remove.get_full_name()} удалён из чата.")
    return redirect("chat:chat_detail", room_id=room.id)


@login_required
def edit_message(request, message_id):
    msg = get_object_or_404(ChatMessage, id=message_id)
    if msg.sender != request.user:
        messages.error(request, "Нельзя редактировать чужое сообщение")
        return redirect("chat:chat_detail", room_id=msg.room.id)
    if request.method == "POST":
        new_content = request.POST.get("content", "").strip()
        if new_content:
            msg.content = new_content
            msg.edited = True
            msg.edited_at = timezone.now()
            msg.save()
            messages.success(request, "Сообщение отредактировано")
    return redirect("chat:chat_detail", room_id=msg.room.id)


@login_required
def delete_message(request, message_id):
    msg = get_object_or_404(ChatMessage, id=message_id)
    if msg.sender != request.user:
        messages.error(request, "Нельзя удалять чужое сообщение")
        return redirect("chat:chat_detail", room_id=msg.room.id)
    if request.method == "POST":
        msg.delete()
        messages.success(request, "Сообщение удалено")
    return redirect("chat:chat_detail", room_id=msg.room.id)


@login_required
def upload_attachment(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in room.participants.all():
        return JsonResponse({"error": "Нет доступа"}, status=403)
    if request.method == "POST" and request.FILES.get("attachment"):
        file = request.FILES["attachment"]
        content_type = file.content_type
        if content_type.startswith("image/"):
            att_type = "image"
        elif content_type.startswith("video/"):
            att_type = "video"
        else:
            att_type = "file"
        msg = ChatMessage.objects.create(
            room=room,
            sender=request.user,
            content="",
            attachment=file,
            attachment_type=att_type,
        )
        msg_data = {
            "id": msg.id,
            "sender": request.user.username,
            "content": "",
            "timestamp": msg.timestamp.strftime("%H:%M %d.%m.%Y"),
            "edited": False,
            "attachment_url": msg.attachment.url,
            "attachment_type": att_type,
            "sender_full_name": (
                request.user.get_full_name()
                if request.user.get_full_name()
                else request.user.username
            ),
        }
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{room_id}", {"type": "chat_message", "data": msg_data}
        )
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "Bad request"}, status=400)


@login_required
def mark_as_read(request, room_id):
    try:
        room = ChatRoom.objects.get(id=room_id)
        unread_messages = room.messages.exclude(sender=request.user).exclude(
            read_by=request.user
        )
        if unread_messages.exists():
            for msg in unread_messages:
                msg.read_by.add(request.user)
        return JsonResponse({"status": "success"})
    except ChatRoom.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Room not found"}, status=404
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
