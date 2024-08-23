from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Sport(models.Model):
    SPORT_NAME = models.CharField(max_length=100)
    SPORT_RULES_AND_REGULATIONS = models.TextField()
    EDITED_AT = models.DateTimeField(default=timezone.now)
    IMAGE = models.ImageField(upload_to='sports_icon/', null=True, blank=True)
    def __str__(self):
        return self.SPORT_NAME

'''
TEAM	                USER	
PK	TEAM_ID		        PK	USER_ID	
    TEAM_NAME		        USER_USERNAME	
    TEAM_TYPE		        USER_EMAIL
    TEAM_SCORE	            USER_PASSWORD
FK	SPORTS_ID		        USER_TYPE
    COACH_ID                USER_INV_CODE
                            IS_COACH
                            IS_ATHLETE
                            IS_SCOUT
                            IS_EVENT_ORG
                            IS_ADMIN
                        FK	PROF_ID		
    
'''

