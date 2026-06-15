from .models import ChatMessage

def unread_chats_counter(request):
    if request.user.is_authenticated:
        try:
            # Считаем уникальные комнаты чатов (distinct), в которых есть 
            # новые сообщения от других пользователей
            unread_count = ChatMessage.objects.filter(
                room__participants=request.user
            ).exclude(
                sender=request.user
            ).exclude(
                read_by=request.user
            ).values('room_id').distinct().count()
        except Exception:
            unread_count = 0
        return {'unread_chats_count': unread_count}
    return {'unread_chats_count': 0}