from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Scan, Appointment, Payment
import logging

logger = logging.getLogger('api')

@shared_task
def process_scan(scan_id):
    try:
        scan = Scan.objects.get(id=scan_id)
        logger.info(f"Processing scan {scan_id}")
        
        # Simulate scan processing
        scan.status = 'processing'
        scan.save()
        
        # TODO: Implement actual scan processing logic
        
        scan.status = 'completed'
        scan.save()
        
        logger.info(f"Scan {scan_id} processed successfully")
        return True
    except Exception as e:
        logger.error(f"Error processing scan {scan_id}: {str(e)}")
        return False

@shared_task
def send_appointment_reminder(appointment_id):
    try:
        appointment = Appointment.objects.get(id=appointment_id)
        logger.info(f"Sending reminder for appointment {appointment_id}")
        
        subject = 'Appointment Reminder'
        message = f"""
        Dear {appointment.user.get_full_name()},
        
        This is a reminder for your appointment with Dr. {appointment.doctor.user.get_full_name()}
        scheduled for {appointment.date_time}.
        
        Best regards,
        Your Healthcare Team
        """
        
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [appointment.user.email],
            fail_silently=False,
        )
        
        logger.info(f"Reminder sent for appointment {appointment_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending reminder for appointment {appointment_id}: {str(e)}")
        return False

@shared_task
def process_payment(payment_id):
    try:
        payment = Payment.objects.get(id=payment_id)
        logger.info(f"Processing payment {payment_id}")
        
        # Simulate payment processing
        payment.status = 'processing'
        payment.save()
        
        # TODO: Implement actual payment processing logic
        
        payment.status = 'completed'
        payment.save()
        
        logger.info(f"Payment {payment_id} processed successfully")
        return True
    except Exception as e:
        logger.error(f"Error processing payment {payment_id}: {str(e)}")
        return False

@shared_task
def cleanup_expired_tokens():
    try:
        from rest_framework.authtoken.models import Token
        from django.utils import timezone
        from datetime import timedelta
        
        expired_tokens = Token.objects.filter(
            created__lt=timezone.now() - timedelta(hours=24)
        )
        count = expired_tokens.count()
        expired_tokens.delete()
        
        logger.info(f"Cleaned up {count} expired tokens")
        return count
    except Exception as e:
        logger.error(f"Error cleaning up expired tokens: {str(e)}")
        return 0

@shared_task
def send_notification(user_id, title, message):
    try:
        from .models import User
        user = User.objects.get(id=user_id)
        
        # TODO: Implement push notification logic
        
        logger.info(f"Notification sent to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending notification to user {user_id}: {str(e)}")
        return False 