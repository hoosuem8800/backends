from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
import os

# Helper function to clean media paths
def clean_media_path(instance, filename):
    """
    Clean the uploaded file path to prevent path duplication issues.
    If the filename already starts with the upload_to folder, remove it.
    """
    # Get the base filename without path
    base_filename = os.path.basename(filename)
    
    # Remove any 'media/' prefix from the filename
    if base_filename.startswith('media/'):
        base_filename = base_filename.replace('media/', '', 1)
    
    # Return the proper path without any duplicate 'media/' prefix
    return f'profile_pictures/{base_filename}'

def clean_doctor_profile_path(instance, filename):
    """
    Clean the uploaded file path for doctor profile pictures.
    Prevents path duplication issues.
    """
    # Get the base filename without path
    base_filename = os.path.basename(filename)
    
    # Remove any 'media/' prefix from the filename
    if base_filename.startswith('media/'):
        base_filename = base_filename.replace('media/', '', 1)
    
    # Return the proper path without any duplicate 'media/' prefix
    return f'doctor_profiles/{base_filename}'

class User(AbstractUser):
    ROLE_CHOICES = [
        ('patient', 'Patient'),
        ('assistant', 'Assistant'),
        ('doctor', 'Doctor'),
        ('admin', 'Admin'),
    ]
    
    SUBSCRIPTION_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patient')
    subscription_type = models.CharField(max_length=10, choices=SUBSCRIPTION_CHOICES, default='free')
    location = models.CharField(max_length=100, blank=True, null=True)
    
    # Add related_name to avoid clashes with auth.User
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='api_user_set',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='api_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

class Doctor(models.Model):
    SPECIALTY_CHOICES = [
        ('cardiology', 'Cardiology'),
        ('neurology', 'Neurology'),
        ('orthopedics', 'Orthopedics'),
        ('dermatology', 'Dermatology'),
        ('pediatrics', 'Pediatrics'),
        ('general', 'General Medicine'),
        ('pulmonology', 'Pulmonology'),
        ('radiology', 'Radiology'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    specialty = models.CharField(max_length=50, choices=SPECIALTY_CHOICES, default='general')
    years_of_experience = models.PositiveIntegerField(default=0)
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    license_number = models.CharField(max_length=50, unique=True)
    profile_picture = models.ImageField(upload_to=clean_doctor_profile_path, null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    education = models.TextField(blank=True, null=True)
    awards = models.TextField(blank=True, null=True)
    languages = models.CharField(max_length=200, blank=True, null=True, help_text="Languages spoken, comma separated")
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    available_days = models.JSONField(default=list)  # List of days the doctor is available
    available_hours = models.JSONField(default=dict)  # Dict of available hours for each day
    is_accepting_new_patients = models.BooleanField(default=True)
    rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(5.00)]
    )
    total_consultations = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name()} - {self.get_specialty_display()}"

    class Meta:
        ordering = ['-rating', '-years_of_experience']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # If this user also has a UserProfile, sync the profile picture
        if hasattr(self.user, 'profile') and self.profile_picture:
            if self.user.profile.profile_picture != self.profile_picture:
                self.user.profile.profile_picture = self.profile_picture
                self.user.profile.save(update_fields=['profile_picture'])

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to=clean_media_path, blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
        
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # If this user is also a doctor, sync the profile picture
        if hasattr(self.user, 'doctor_profile') and self.profile_picture:
            if self.user.doctor_profile.profile_picture != self.profile_picture:
                self.user.doctor_profile.profile_picture = self.profile_picture
                self.user.doctor_profile.save(update_fields=['profile_picture'])

# Signal to sync profile picture when UserProfile is created or updated
@receiver(post_save, sender=Doctor)
def sync_doctor_profile_picture(sender, instance, created, **kwargs):
    if created and instance.profile_picture and hasattr(instance.user, 'profile'):
        instance.user.profile.profile_picture = instance.profile_picture
        instance.user.profile.save(update_fields=['profile_picture'])

@receiver(post_save, sender=UserProfile)
def sync_user_profile_picture(sender, instance, created, **kwargs):
    if created and instance.profile_picture and hasattr(instance.user, 'doctor_profile'):
        instance.user.doctor_profile.profile_picture = instance.profile_picture
        instance.user.doctor_profile.save(update_fields=['profile_picture'])

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments')
    date_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='confirmed')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Appointment for {self.user.username} on {self.date_time}"
        
    def save(self, *args, **kwargs):
        # IMPORTANT: Ensure date_time is saved as a naive datetime without timezone
        # information to prevent any timezone conversion issues
        if self.date_time:
            # If date_time is timezone aware (has tzinfo), remove timezone info
            if hasattr(self.date_time, 'tzinfo') and self.date_time.tzinfo:
                # Convert to naive datetime by removing tzinfo
                self.date_time = self.date_time.replace(tzinfo=None)
        
        # Call the original save method
        super().save(*args, **kwargs)

class Scan(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]
    
    RESULT_CHOICES = [
        ('healthy', 'Healthy'),
        ('requires_consultation', 'Requires Consultation'),
        ('inconclusive', 'Inconclusive'),
        ('optional_consultation', 'Optional Consultation')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scans')
    image = models.ImageField(upload_to='scans/')
    upload_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result = models.TextField(blank=True, null=True)
    result_status = models.CharField(max_length=25, choices=RESULT_CHOICES, default='inconclusive')
    confidence_score = models.FloatField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    requires_consultation = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Scan {self.id} - {self.user.username}"

class Consultation(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_consultations')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doctor_consultations')
    scan = models.ForeignKey(Scan, on_delete=models.SET_NULL, null=True, blank=True, related_name='consultations')
    consultation_type = models.CharField(max_length=20, choices=[
        ('initial', 'Initial'),
        ('follow_up', 'Follow-up'),
        ('emergency', 'Emergency')
    ], default='initial')
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='pending')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Consultation for {self.patient.get_full_name()} with Dr. {self.doctor.get_full_name()}"

    def mark_as_completed(self):
        self.status = 'completed'
        self.save()

    def schedule_follow_up(self):
        Consultation.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            consultation_type='follow_up',
            status='pending'
        )

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded')
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('net_banking', 'Net Banking'),
        ('upi', 'UPI')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Payment {self.transaction_id} - {self.user.username}"

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('appointment', 'Appointment'),
        ('scan', 'Scan'),
        ('payment', 'Payment'),
        ('system', 'System'),
        ('xray', 'X-Ray'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='system')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type} notification for {self.user.username}"

class XRayImage(models.Model):
    appointment = models.ForeignKey('Appointment', on_delete=models.CASCADE, related_name='xray_images')
    image = models.ImageField(upload_to='xray_images/')
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='xray_images')
    assistant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_xray_images')
    upload_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"X-ray for {self.patient.get_full_name()} uploaded by {self.assistant.get_full_name()}"

class Creator(models.Model):
    """
    Model to represent creators/team members with their role and contribution information
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='creator_profile')
    job_title = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    contribution = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.job_title}"
