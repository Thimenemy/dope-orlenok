from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [

    path('', views.chat_list, name='chat_list'),
    path('room/<int:room_id>/', views.chat_detail, name='chat_detail'),
    path('create/', views.create_chat, name='create_chat'),   # новый
    path('private/<int:user_id>/', views.create_private_chat, name='create_private_chat'),
    path('delete_for_me/<int:room_id>/', views.delete_chat_for_me, name='delete_for_me'),
    path('restore_for_user/<int:room_id>/', views.restore_for_user, name='restore_for_user'),
    path('delete_permanently/<int:room_id>/', views.delete_chat_permanently, name='delete_permanently'),
    path('invite/<int:room_id>/', views.invite_to_group_chat, name='invite_to_group'),
    path('remove/<int:room_id>/<int:user_id>/', views.remove_from_group_chat, name='remove_from_group'),
    path('upload/<int:room_id>/', views.upload_attachment, name='upload_attachment'),
    path('edit_message/<int:message_id>/', views.edit_message, name='edit_message'),
    path('delete_message/<int:message_id>/', views.delete_message, name='delete_message'),
]
