import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, ChatMessage

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        if not await self.user_in_room():
            await self.close()
            return
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        # Текстовое сообщение
        if data.get('type') == 'message':
            message = data['message']
            user = self.scope['user']
            saved = await self.save_message(user, message, None, None)
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'chat_message', 'data': saved}
            )
            return  # не идём дальше
        # Данные от upload_attachment (уже полный объект сообщения)
        await self.channel_layer.group_send(
            self.room_group_name,
            {'type': 'chat_message', 'data': data}
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['data']))

    @database_sync_to_async
    def user_in_room(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            return room.participants.filter(id=self.scope['user'].id).exists()
        except:
            return False

    @database_sync_to_async
    def save_message(self, user, message, attachment, att_type):
        room = ChatRoom.objects.get(id=self.room_id)
        msg = ChatMessage.objects.create(
            room=room,
            sender=user,
            content=message,
            attachment=attachment,
            attachment_type=att_type
        )
        return self.message_to_dict(msg)

    def message_to_dict(self, msg):
        attachment_url = None
        if msg.attachment:
            # Если url не начинается с /media/, принудительно добавляем его
            attachment_url = msg.attachment.url if msg.attachment.url.startswith('http') or msg.attachment.url.startswith('/') else f'/media/{msg.attachment.name}'
            
        return {
            'id': msg.id,
            'sender': msg.sender.username,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%H:%M %d.%m.%Y'),
            'edited': msg.edited,
            'attachment_url': attachment_url,
            'attachment_type': msg.attachment_type,
        }