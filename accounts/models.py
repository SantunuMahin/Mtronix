from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User


class UserProfile(models.Model):
    SYSTEMOWNER = 'SYSTEM_OWNER'
    ADMIN = 'admin'
    MANAGER = 'manager'
    STOREKEEPER = 'storekeeper'
    SALES = 'sales'

    ROLE_CHOICES = [
        (SYSTEMOWNER, 'System Owner'),
        (ADMIN, 'Admin'),
        (MANAGER, 'Manager'),
        (STOREKEEPER, 'Storekeeper'),
        (SALES, 'Sales'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STOREKEEPER)
    SYSTEM_OWNER = SYSTEMOWNER

    @property
    def is_system_owner(self):
        return self.role == self.SYSTEMOWNER

    @property
    def is_SYSTEM_OWNER(self):
        return self.role == self.SYSTEMOWNER

    @property
    def is_admin(self):
        return self.role == self.ADMIN

    @property
    def is_manager(self):
        return self.role == self.MANAGER

    @property
    def is_storekeeper(self):
        return self.role == self.STOREKEEPER

    @property
    def is_sales(self):
        return self.role == self.SALES

    def __str__(self):
        return f'{self.user.username} - {self.get_role_display()}'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
