from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import random
from api.models import (
    UserProfile, DoctorProfile, Scan, Appointment, Payment,
    Notification, Review
)
from faker import Faker
import logging

logger = logging.getLogger('api')
fake = Faker()

class Command(BaseCommand):
    help = 'Generates test data for development purposes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of users to create (default: 10)'
        )
        parser.add_argument(
            '--doctors',
            type=int,
            default=5,
            help='Number of doctors to create (default: 5)'
        )
        parser.add_argument(
            '--scans',
            type=int,
            default=20,
            help='Number of scans to create (default: 20)'
        )
        parser.add_argument(
            '--appointments',
            type=int,
            default=30,
            help='Number of appointments to create (default: 30)'
        )

    def handle(self, *args, **options):
        User = get_user_model()
        num_users = options['users']
        num_doctors = options['doctors']
        num_scans = options['scans']
        num_appointments = options['appointments']

        self.stdout.write("Generating test data...")

        # Create users
        users = []
        for _ in range(num_users):
            user = User.objects.create_user(
                username=fake.user_name(),
                email=fake.email(),
                password='testpass123',
                first_name=fake.first_name(),
                last_name=fake.last_name()
            )
            UserProfile.objects.create(
                user=user,
                phone_number=fake.phone_number(),
                address=fake.address(),
                date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=80)
            )
            users.append(user)
        self.stdout.write(f"Created {len(users)} users")

        # Create doctors
        doctors = []
        for _ in range(num_doctors):
            user = User.objects.create_user(
                username=fake.user_name(),
                email=fake.email(),
                password='testpass123',
                first_name=fake.first_name(),
                last_name=fake.last_name()
            )
            profile = UserProfile.objects.create(
                user=user,
                phone_number=fake.phone_number(),
                address=fake.address(),
                date_of_birth=fake.date_of_birth(minimum_age=25, maximum_age=70)
            )
            doctor = DoctorProfile.objects.create(
                user=user,
                specialization=random.choice(['Cardiology', 'Neurology', 'Orthopedics', 'Dermatology']),
                license_number=fake.uuid4(),
                years_of_experience=random.randint(1, 30),
                consultation_fee=random.randint(100, 1000)
            )
            doctors.append(doctor)
        self.stdout.write(f"Created {len(doctors)} doctors")

        # Create scans
        scans = []
        for _ in range(num_scans):
            scan = Scan.objects.create(
                user=random.choice(users),
                scan_type=random.choice(['MRI', 'CT', 'X-Ray', 'Ultrasound']),
                upload_date=timezone.now() - timedelta(days=random.randint(0, 30)),
                status=random.choice(['pending', 'completed', 'failed']),
                result='Test result',
                file_path=f'/scans/test_scan_{fake.uuid4()}.dcm'
            )
            scans.append(scan)
        self.stdout.write(f"Created {len(scans)} scans")

        # Create appointments
        appointments = []
        for _ in range(num_appointments):
            appointment = Appointment.objects.create(
                user=random.choice(users),
                doctor=random.choice(doctors),
                date_time=timezone.now() + timedelta(days=random.randint(1, 30)),
                status=random.choice(['scheduled', 'completed', 'cancelled']),
                reason=fake.text(max_nb_chars=200),
                notes=fake.text(max_nb_chars=500)
            )
            appointments.append(appointment)
        self.stdout.write(f"Created {len(appointments)} appointments")

        # Create payments
        for appointment in appointments:
            if appointment.status == 'completed':
                Payment.objects.create(
                    user=appointment.user,
                    appointment=appointment,
                    amount=appointment.doctor.consultation_fee,
                    status=random.choice(['completed', 'failed', 'refunded']),
                    payment_method=random.choice(['credit_card', 'bank_transfer']),
                    transaction_id=fake.uuid4()
                )
        self.stdout.write(f"Created payments for completed appointments")

        # Create notifications
        for user in users:
            for _ in range(random.randint(1, 5)):
                Notification.objects.create(
                    user=user,
                    title=fake.sentence(),
                    message=fake.text(max_nb_chars=200),
                    notification_type=random.choice(['appointment', 'scan', 'payment', 'system']),
                    is_read=random.choice([True, False])
                )
        self.stdout.write("Created notifications for users")

        # Create reviews
        for appointment in appointments:
            if appointment.status == 'completed':
                Review.objects.create(
                    user=appointment.user,
                    doctor=appointment.doctor,
                    rating=random.randint(1, 5),
                    comment=fake.text(max_nb_chars=500),
                    created_at=appointment.date_time + timedelta(days=1)
                )
        self.stdout.write("Created reviews for completed appointments")

        self.stdout.write("Test data generation completed successfully") 