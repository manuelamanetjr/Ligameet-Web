from django.db import models
from django.contrib.auth.models import User
import shortuuid
from ligameet.models import Team

class ChatGroup(models.Model):
    group_name = models.CharField(max_length=128, unique=True, blank=True)
    groupchat_name = models.CharField(max_length=128, null=True, blank=True)
    admin = models.ForeignKey(User, related_name='groupchats', blank=True, null=True, on_delete=models.SET_NULL)
    users_online = models.ManyToManyField(User, related_name='online_in_groups', blank=True)
    members = models.ManyToManyField(User, related_name='chat_groups', blank=True)
    is_private = models.BooleanField(default=False)
    team = models.ForeignKey(Team , on_delete=models.CASCADE, related_name='chat_groups', null=True, blank=True)

    def __str__(self):
        return self.group_name
    
    def has_unread_messages(self, user):
        return self.chat_messages.filter(is_read=False).exclude(author=user).exists()

    
    def save(self, *args, **kwargs):
        if not self.group_name:
            self.group_name = shortuuid.uuid()
        super().save(*args, **kwargs)

    

class GroupMessage(models.Model):
    group = models.ForeignKey(ChatGroup, related_name='chat_messages', on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.CharField(max_length=300)
    created = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.author.username} : {self.body} - {self.is_read}'
    
    class Meta:
        ordering = ['-created']
        