from django.urls import path
from .views import *

urlpatterns = [
    path('', chat_view, name="chat-home"),
    path('<username>', get_or_create_chatroom, name="start-chat"),
    path('room/<chatroom_name>', chat_view, name="chatroom"),
    path('new_groupchat/', create_groupchat, name="new-groupchat"),
    path('edit/<chatroom_name>', chatroom_edit_view, name="edit-chatroom"),
]
