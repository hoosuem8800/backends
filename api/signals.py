from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserProfile
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        try:
            UserProfile.objects.create(user=instance)
            logger.info(f"Created user profile for {instance.username}")
        except Exception as e:
            logger.error(f"Error creating profile for {instance.username}: {str(e)}")

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, created, **kwargs):
    if not created:
        try:
            if hasattr(instance, 'profile'):
                instance.profile.save()
                logger.info(f"Saved user profile for {instance.username}")
        except Exception as e:
            logger.error(f"Error saving profile for {instance.username}: {str(e)}") 