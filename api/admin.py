from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserProfile, Scan, Appointment, Payment, Notification, Consultation, Doctor, XRayImage, Creator

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'subscription_type', 'location', 'is_staff')
    list_filter = ('role', 'subscription_type', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'location')
    ordering = ('username',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'location')}),
        ('Permissions', {'fields': ('role', 'subscription_type', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role', 'subscription_type', 'location'),
        }),
    )

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number')
    search_fields = ('user__username', 'user__email', 'phone_number')
    raw_id_fields = ('user',)

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialty', 'years_of_experience', 'gender', 'age', 'rating', 'is_accepting_new_patients')
    list_filter = ('specialty', 'gender', 'is_accepting_new_patients')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'license_number', 'bio', 'education', 'languages')
    raw_id_fields = ('user',)

@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ('user', 'upload_date', 'status')
    list_filter = ('status', 'upload_date')
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user',)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_time', 'status')
    list_filter = ('status', 'date_time')
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user',)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'payment_method', 'transaction_id')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'transaction_id')
    raw_id_fields = ('user',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    raw_id_fields = ('user',)

@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'consultation_type', 'status', 'created_at')
    list_filter = ('status', 'consultation_type')
    search_fields = ('patient__username', 'doctor__username', 'notes')
    raw_id_fields = ('patient', 'doctor', 'scan')

@admin.register(XRayImage)
class XRayImageAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'patient', 'assistant', 'upload_date')
    list_filter = ('upload_date',)
    search_fields = ('patient__username', 'patient__first_name', 'patient__last_name',
                    'assistant__username', 'assistant__first_name', 'assistant__last_name',
                    'notes')
    raw_id_fields = ('appointment', 'patient', 'assistant')
    readonly_fields = ('upload_date',)
    date_hierarchy = 'upload_date'

@admin.register(Creator)
class CreatorAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'job_title', 'role', 'is_active')
    list_filter = ('is_active', 'role', 'job_title')
    search_fields = ('user__first_name', 'user__last_name', 'user__email', 'job_title', 'role')
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Name'
