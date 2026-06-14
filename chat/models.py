from django.db import models
from django.conf import settings

class ChatRoom(models.Model):
    TYPE_CHOICES = (
        ('group', 'Групповой'),
        ('private', 'Личный'),
    )
    room_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='private')
    name = models.CharField(max_length=255, blank=True, null=True)  # для групповых чатов
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_rooms')
    teacher_group = models.ForeignKey('teacher.Group', on_delete=models.SET_NULL, null=True, blank=True, related_name='chat_rooms')  # связь с учебной группой
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_chats')
    deleted_for = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='hidden_chats',
        blank=True,
        help_text='Пользователи, для которых чат считается удалённым (скрыт из списка)')

    def __str__(self):
        if self.room_type == 'group':
            return self.name or f"Group chat {self.id}"
        return f"Private {', '.join([u.username for u in self.participants.all()])}"

class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    attachment = models.FileField(upload_to='chat_attachments/%Y/%m/%d/', null=True, blank=True)  # важно!
    attachment_type = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender}: {self.content[:20]}"