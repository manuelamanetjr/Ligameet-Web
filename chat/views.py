from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from .models import *
from .forms import * 

@login_required
def chat_view(request, chatroom_name='public-chat'):
    chat_group = get_object_or_404(ChatGroup, group_name=chatroom_name)
    chat_messages = chat_group.chat_messages.all()[:30]
    form = ChatmessageCreateForm()

    other_user = None
    if chat_group.is_private:
        if request.user not in chat_group.members.all():
            raise Http404()
        for member in chat_group.members.all():
            if member != request.user:
                other_user = member #get the user to be used in chat.html
                break
    #add member to groupchat            
    if chat_group.groupchat_name:   #is a groupchat
        if request.user not in chat_group.members.all():
            chat_group.members.add(request.user) #add

    if request.htmx:
        form = ChatmessageCreateForm(request.POST)
        if form.is_valid:
            message = form.save(commit=False)
            message.author = request.user
            message.group = chat_group
            message.save()
            context = {
                'message': message,
                'user': request.user
            }
            return render(request, 'chat/partials/chat_message_p.html', context)

    context = {
        'chat_messages': chat_messages, 
        'form': form,
        'other_user': other_user,
        'chatroom_name': chatroom_name, #to establish websocket connection 
        'chat_group': chat_group
    }

    return render(request, 'chat/chat.html', context)

@login_required
def get_or_create_chatroom(request, username):
    other_user = User.objects.get(username = username)
    my_private_chatrooms = request.user.chat_groups.filter(is_private=True)

    if my_private_chatrooms.exists():
        for chatroom in my_private_chatrooms:
            if other_user in chatroom.members.all(): #check if user is member of chatrooom
                return redirect('chatroom', chatroom.group_name)

    chatroom = ChatGroup.objects.create( is_private = True )
    chatroom.members.add(other_user, request.user)   
    return redirect('chatroom', chatroom.group_name)

@login_required
def create_groupchat(request):
    form = NewGroupForm()

    if request.method == 'POST':
        form = NewGroupForm(request.POST)
        if form.is_valid():
            new_groupchat = form.save(commit=False) #to add admin property
            new_groupchat.admin = request.user
            new_groupchat.save()
            new_groupchat.members.add(request.user)
            return redirect('chatroom', new_groupchat.group_name)
    context = {
        'form': form
    }
    return render(request, 'chat/create_groupchat.html', context)

