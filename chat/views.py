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

User = get_user_model()

def is_teacher(user):
    return user.groups.filter(name="Преподаватель").exists()

def is_parent(user):
    return user.groups.filter(name="Родитель").exists()

def get_base_template(user):
    if user.groups.filter(name='Преподаватель').exists():
        return 'teacher/base_teacher.html'
    return 'home/base_auth.html'

@login_required
def chat_list(request):
    rooms = request.user.chat_rooms.exclude(deleted_for=request.user).order_by('-updated_at')
    rooms_data = []
    for room in rooms:
        if room.room_type == 'group':
            display_name = room.name or 'Групповой чат'
        else:
            other = room.participants.exclude(id=request.user.id).first()
            if other:
                display_name = f"{other.last_name} {other.first_name}".strip() or other.username
            else:
                display_name = 'Неизвестный участник'
        rooms_data.append({'room': room, 'display_name': display_name})
    is_teacher = request.user.groups.filter(name='Преподаватель').exists()
    base_template = get_base_template(request.user)
    hidden_rooms = []
    if is_teacher:
        hidden_rooms = ChatRoom.objects.filter(deleted_for__isnull=False).exclude(deleted_for=request.user).distinct()
    return render(request, 'chat/chat_list.html', {
        'rooms_data': rooms_data,
        'is_teacher': is_teacher,
        'is_parent': not is_teacher,
        'base_template': base_template,
        'hidden_rooms': hidden_rooms,
    })

@login_required
def chat_detail(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in room.participants.all():
        messages.error(request, 'Нет доступа')
        return redirect('chat:chat_list')
    messages_history = room.messages.all()
    base_template = get_base_template(request.user)
    is_teacher = request.user.groups.filter(name='Преподаватель').exists()

    from_group = request.GET.get('from_group')
    back_url = None
    if from_group and is_teacher:
        try:
            group_id = int(from_group)
            if request.user.teaching_groups.filter(id=group_id).exists():
                back_url = reverse('teacher:group_detail', args=[group_id]) + '#chats-tab'
        except ValueError:
            pass

    other_participant = None
    if room.room_type == 'private':
        other_participant = room.participants.exclude(id=request.user.id).first()

    available_users = []
    if room.room_type == 'group' and (room.created_by == request.user or is_teacher):
        available_users = User.objects.exclude(id__in=room.participants.all()).exclude(id=request.user.id)

    context = {
        'room': room,
        'messages': messages_history,
        'base_template': base_template,
        'back_url': back_url,
        'is_teacher': is_teacher,
        'other_participant': other_participant,
        'available_users': available_users,
    }
    return render(request, 'chat/chat_detail.html', context)

@login_required
def create_chat(request):
    if request.method == 'POST':
        form = CreateChatForm(request.POST, user=request.user)
        if form.is_valid():
            chat_type = form.cleaned_data['chat_type']
            name = form.cleaned_data.get('name')
            participants = list(form.cleaned_data['participants'])
            if chat_type == 'private':
                other = participants[0] if participants else None
                if other:
                    existing = ChatRoom.objects.filter(
                        room_type='private',
                        participants=request.user
                    ).filter(participants=other).distinct().first()
                    if existing:
                        return redirect('chat:chat_detail', room_id=existing.id)
                room = ChatRoom.objects.create(room_type='private', created_by=request.user)
                room.participants.add(request.user, other)
                return redirect('chat:chat_detail', room_id=room.id)
            elif chat_type == 'group':
                if not name:
                    form.add_error('name', 'Укажите название группового чата')
                else:
                    existing = ChatRoom.objects.filter(
                        room_type='group',
                        name=name,
                        participants=request.user
                    ).first()
                    if existing:
                        return redirect('chat:chat_detail', room_id=existing.id)
                    room = ChatRoom.objects.create(room_type='group', name=name, created_by=request.user)
                    room.participants.set(participants + [request.user])
                    return redirect('chat:chat_detail', room_id=room.id)
    else:
        form = CreateChatForm(user=request.user)
    base_template = get_base_template(request.user)
    return render(request, 'chat/create_chat.html', {'form': form, 'base_template': base_template})

@login_required
def create_private_chat(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    existing = ChatRoom.objects.filter(
        room_type='private',
        participants=request.user
    ).filter(participants=other_user).distinct().first()
    if existing:
        if existing.deleted_for.filter(id=request.user.id).exists():
            existing.deleted_for.remove(request.user)
        return redirect('chat:chat_detail', room_id=existing.id)
    room = ChatRoom.objects.create(room_type='private', created_by=request.user)
    room.participants.add(request.user, other_user)
    return redirect('chat:chat_detail', room_id=room.id)

@login_required
def delete_chat_for_me(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in room.participants.all():
        messages.error(request, 'Нет доступа')
        return redirect('chat:chat_list')
    room.deleted_for.add(request.user)
    messages.success(request, 'Чат скрыт из вашего списка')
    return redirect('chat:chat_list')

@login_required
@user_passes_test(is_teacher)
def delete_chat_permanently(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in room.participants.all():
        messages.error(request, 'Нет доступа')
        return redirect('chat:chat_list')
    room.delete()
    messages.success(request, 'Чат удалён полностью')
    return redirect('chat:chat_list')

@login_required
@user_passes_test(is_teacher)
def restore_for_user(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    room.deleted_for.clear()
    messages.success(request, 'Чат восстановлен для всех участников.')
    return redirect('chat:chat_list')

@login_required
def invite_to_group_chat(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    # Разрешаем действие, если это группа И (пользователь — создатель ИЛИ он преподаватель)
    is_teacher_user = request.user.groups.filter(name="Преподаватель").exists()
    if room.room_type != 'group' or (room.created_by != request.user and not is_teacher_user):
        messages.error(request, 'У вас нет прав для управления участниками этого чата.')
        return redirect('chat:chat_detail', room_id=room.id)
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_user = get_object_or_404(User, id=user_id)
        if new_user in room.participants.all():
            messages.warning(request, 'Пользователь уже в чате.')
        else:
            room.participants.add(new_user)
            room.deleted_for.remove(new_user)
            messages.success(request, f'{new_user.get_full_name()} добавлен в чат.')
    return redirect('chat:chat_detail', room_id=room.id)

@login_required
def remove_from_group_chat(request, room_id, user_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    # Разрешаем действие, если это группа И (пользователь — создатель ИЛИ он преподаватель)
    is_teacher_user = request.user.groups.filter(name="Преподаватель").exists()
    if room.room_type != 'group' or (room.created_by != request.user and not is_teacher_user):
        messages.error(request, 'У вас нет прав для управления участниками этого чата.')
        return redirect('chat:chat_detail', room_id=room.id)
    user_to_remove = get_object_or_404(User, id=user_id)
    if user_to_remove == room.created_by:
        messages.error(request, 'Нельзя исключить создателя чата.')
        return redirect('chat:chat_detail', room_id=room.id)
    room.participants.remove(user_to_remove)
    room.deleted_for.remove(user_to_remove)
    messages.success(request, f'{user_to_remove.get_full_name()} удалён из чата.')
    return redirect('chat:chat_detail', room_id=room.id)

@login_required
def edit_message(request, message_id):
    msg = get_object_or_404(ChatMessage, id=message_id)
    if msg.sender != request.user:
        messages.error(request, 'Нельзя редактировать чужое сообщение')
        return redirect('chat:chat_detail', room_id=msg.room.id)
    if request.method == 'POST':
        new_content = request.POST.get('content', '').strip()
        if new_content:
            msg.content = new_content
            msg.edited = True
            msg.edited_at = timezone.now()
            msg.save()
            messages.success(request, 'Сообщение отредактировано')
    return redirect('chat:chat_detail', room_id=msg.room.id)

@login_required
def delete_message(request, message_id):
    msg = get_object_or_404(ChatMessage, id=message_id)
    if msg.sender != request.user:
        messages.error(request, 'Нельзя удалять чужое сообщение')
        return redirect('chat:chat_detail', room_id=msg.room.id)
    if request.method == 'POST':
        msg.delete()
        messages.success(request, 'Сообщение удалено')
    return redirect('chat:chat_detail', room_id=msg.room.id)

@login_required
def upload_attachment(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in room.participants.all():
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    if request.method == 'POST' and request.FILES.get('attachment'):
        file = request.FILES['attachment']
        content_type = file.content_type
        if content_type.startswith('image/'):
            att_type = 'image'
        elif content_type.startswith('video/'):
            att_type = 'video'
        else:
            att_type = 'file'
        msg = ChatMessage.objects.create(
            room=room,
            sender=request.user,
            content='',
            attachment=file,
            attachment_type=att_type
        )
        msg_data = {
            'id': msg.id,
            'sender': request.user.username,
            'content': '',
            'timestamp': msg.timestamp.strftime('%H:%M %d.%m.%Y'),
            'edited': False,
            'attachment_url': msg.attachment.url,
            'attachment_type': att_type,
        }
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{room_id}',
            {'type': 'chat_message', 'data': msg_data}
        )
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'Bad request'}, status=400)