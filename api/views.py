from django.shortcuts import render # type: ignore
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
import logging
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied, APIException
from django.contrib.auth.models import Group
from django.db.models import Q
from django.utils import timezone
from rest_framework import filters
from rest_framework_simplejwt.tokens import RefreshToken
import os
import requests
from django.conf import settings
from datetime import datetime, timedelta
from .models import (
    UserProfile, 
    Scan, 
    Appointment, 
    Payment, 
    Notification, 
    Consultation,
    Doctor,
    XRayImage,
    Creator
)
from .serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    UserSerializer,
    ScanSerializer,
    AppointmentSerializer,
    PaymentSerializer,
    ConsultationSerializer,
    DoctorSerializer,
    NotificationSerializer,
    AdminPaymentSerializer,
    AdminConsultationSerializer,
    XRayImageSerializer,
    CreatorSerializer
)
from .filters import ScanFilter, AppointmentFilter, PaymentFilter
import pytz
import uuid
import json
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import NotFound
from django.utils.dateparse import parse_datetime
from .ml_service import ml_service

User = get_user_model()
logger = logging.getLogger(__name__)

class AppointmentConflictException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Appointment time slot is already taken'
    default_code = 'appointment_conflict'

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['role', 'subscription_type']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    def get_permissions(self):
        if self.action in ['register', 'create']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action == 'register':
            return UserRegistrationSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = User.objects.all()
        
        # Admin and staff users can see all users
        if self.request.user.is_staff or self.request.user.role == 'admin':
            return queryset
        
        # Doctors can see their patients (users who have consultations with this doctor)
        if self.request.user.role == 'doctor':
            # Get all patient IDs from consultations where this doctor is involved
            patient_ids = Consultation.objects.filter(doctor=self.request.user).values_list('patient_id', flat=True)
            # Add the doctor's own ID to the queryset
            return queryset.filter(Q(id=self.request.user.id) | Q(id__in=patient_ids))
            
        # Non-admin, non-doctor users can only see their own profile
        return queryset.filter(id=self.request.user.id)
        
    @action(detail=False, methods=['get'])
    def assistants(self, request):
        """Get all users with assistant role"""
        if not request.user.is_staff and not request.user.role == 'assistant':
            return Response(
                {'error': 'Only admin and assistants can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        assistants = User.objects.filter(role='assistant')
        serializer = self.get_serializer(assistants, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'put', 'patch'])
    def profile(self, request):
        """
        Get or update the user's profile.
        """
        user = request.user
        profile = user.profile

        if request.method == 'GET':
            user_serializer = self.get_serializer(user)
            profile_serializer = UserProfileSerializer(profile)
            profile_data = profile_serializer.data
            
            # Add the full profile picture URL if it exists
            if profile.profile_picture:
                request_host = request.get_host()
                profile_picture_url = request.build_absolute_uri(profile.profile_picture.url)
                profile_data['profile_picture_url'] = profile_picture_url
            
            return Response({
                'user': user_serializer.data,
                'profile': profile_data
            })

        try:
            # Handle profile picture upload
            profile_picture = request.FILES.get('profile_picture')
            if profile_picture:
                # Validate file size (max 5MB)
                if profile_picture.size > 5 * 1024 * 1024:
                    return Response(
                        {'error': 'Profile picture must be less than 5MB'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Validate file type
                allowed_types = ['image/jpeg', 'image/png', 'image/gif']
                if profile_picture.content_type not in allowed_types:
                    return Response(
                        {'error': 'Invalid file type. Allowed types: JPEG, PNG, GIF'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Delete old profile picture if it exists
                if profile.profile_picture:
                    try:
                        profile.profile_picture.delete()
                    except Exception as e:
                        print(f"Error deleting old profile picture: {e}")

                # Set new profile picture
                profile.profile_picture = profile_picture

            # Extract profile data from request
            profile_data = {}
            for key, value in request.data.items():
                if key.startswith('profile[') and key.endswith(']'):
                    field = key[8:-1]  # Remove 'profile[' and ']'
                    profile_data[field] = value

            # Update profile
            profile_serializer = UserProfileSerializer(profile, data=profile_data, partial=True)
            if profile_serializer.is_valid():
                profile_serializer.save()
            else:
                return Response(profile_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Update user data
            user_serializer = self.get_serializer(user, data=request.data, partial=True)
            if user_serializer.is_valid():
                user_serializer.save()
            else:
                return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Get updated profile data with full URL
            updated_profile = UserProfileSerializer(profile).data
            if profile.profile_picture:
                request_host = request.get_host()
                profile_picture_url = request.build_absolute_uri(profile.profile_picture.url)
                updated_profile['profile_picture_url'] = profile_picture_url
            
            # Return updated data
            response = Response({
                'user': user_serializer.data,
                'profile': updated_profile
            })
            
            # Set CORS headers for media files
            if profile.profile_picture:
                response['Access-Control-Expose-Headers'] = 'Content-Disposition'
                response['Access-Control-Allow-Origin'] = '*'
                response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Content-Type'
            
            return response

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get', 'put', 'patch'])
    def profile(self, request, pk=None):
        """
        Get or update a specific user's profile.
        """
        try:
            # Get the target user (admins can modify anyone, regular users only themselves)
            if request.user.is_staff or request.user.role == 'admin' or str(request.user.id) == pk:
                user = self.get_object()
            else:
                return Response(
                    {'error': 'You do not have permission to modify this profile'},
                    status=status.HTTP_403_FORBIDDEN
                )
                
            profile = user.profile

            if request.method == 'GET':
                user_serializer = self.get_serializer(user)
                profile_serializer = UserProfileSerializer(profile)
                profile_data = profile_serializer.data
                
                # Add the full profile picture URL if it exists
                if profile.profile_picture:
                    request_host = request.get_host()
                    profile_picture_url = request.build_absolute_uri(profile.profile_picture.url)
                    profile_data['profile_picture_url'] = profile_picture_url
                
                return Response({
                    'user': user_serializer.data,
                    'profile': profile_data
                })

            # Handle profile picture upload
            profile_picture = request.FILES.get('profile_picture')
            if profile_picture:
                # Validate file size (max 5MB)
                if profile_picture.size > 5 * 1024 * 1024:
                    return Response(
                        {'error': 'Profile picture must be less than 5MB'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Validate file type
                allowed_types = ['image/jpeg', 'image/png', 'image/gif']
                if profile_picture.content_type not in allowed_types:
                    return Response(
                        {'error': 'Invalid file type. Allowed types: JPEG, PNG, GIF'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Delete old profile picture if it exists
                if profile.profile_picture:
                    try:
                        profile.profile_picture.delete()
                    except Exception as e:
                        print(f"Error deleting old profile picture: {e}")

                # Set new profile picture
                profile.profile_picture = profile_picture

            # Extract profile data from request
            profile_data = {}
            for key, value in request.data.items():
                if key.startswith('profile[') and key.endswith(']'):
                    field = key[8:-1]  # Remove 'profile[' and ']'
                    profile_data[field] = value

            # Update profile
            profile_serializer = UserProfileSerializer(profile, data=profile_data, partial=True)
            if profile_serializer.is_valid():
                profile_serializer.save()
            else:
                return Response(profile_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Update user data (only if this is the current user or an admin)
            if str(request.user.id) == pk or request.user.is_staff or request.user.role == 'admin':
                user_serializer = self.get_serializer(user, data=request.data, partial=True)
                if user_serializer.is_valid():
                    user_serializer.save()
                else:
                    return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Get updated profile data with full URL
            updated_profile = UserProfileSerializer(profile).data
            if profile.profile_picture:
                request_host = request.get_host()
                profile_picture_url = request.build_absolute_uri(profile.profile_picture.url)
                updated_profile['profile_picture_url'] = profile_picture_url
            
            # Return updated data
            response = Response({
                'user': UserSerializer(user).data,
                'profile': updated_profile
            })
            
            # Set CORS headers for media files
            if profile.profile_picture:
                response['Access-Control-Expose-Headers'] = 'Content-Disposition'
                response['Access-Control-Allow-Origin'] = '*'
                response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Content-Type'
            
            return response

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def register(self, request):
        """
        Register a new user with their profile.
        """
        logger.info("Received registration request")
        logger.debug(f"Request data: {request.data}")
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            logger.info("Registration data is valid")
            try:
                with transaction.atomic():
                    user = serializer.save()
                    token = Token.objects.create(user=user)
                    logger.info(f"User {user.username} registered successfully")
                    return Response({
                        'token': token.key,
                        'user': UserSerializer(user).data
                    }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error during registration: {str(e)}")
                return Response({
                    'error': 'Registration failed',
                    'detail': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logger.warning(f"Registration failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Admin and staff users can see all profiles
        if self.request.user.is_staff or self.request.user.role == 'admin':
            return UserProfile.objects.all()
            
        # Doctors can see profiles of their patients
        if self.request.user.role == 'doctor':
            # Get patient IDs from consultations
            patient_ids = Consultation.objects.filter(doctor=self.request.user).values_list('patient_id', flat=True)
            # Include doctor's own profile
            return UserProfile.objects.filter(Q(user=self.request.user) | Q(user_id__in=patient_ids))
            
        # Regular users can only see their own profile
        return UserProfile.objects.filter(user=self.request.user)

class ConsultationViewSet(viewsets.ModelViewSet):
    queryset = Consultation.objects.all()
    serializer_class = ConsultationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        try:
            user = self.request.user
            if not user or not user.is_authenticated:
                logger.error("Unauthenticated user tried to access consultations")
                return Consultation.objects.none()

            if not hasattr(user, 'role'):
                logger.error(f"User {user.id} has no role attribute")
                return Consultation.objects.none()

            base_queryset = Consultation.objects.select_related('doctor', 'patient').all()

            if user.role == 'admin':
                return base_queryset
            elif user.role == 'doctor':
                return base_queryset.filter(doctor=user)
            else:  # patient or other roles
                return base_queryset.filter(patient=user)

        except Exception as e:
            logger.error(f"Error in ConsultationViewSet.get_queryset: {str(e)}")
            return Consultation.objects.none()

    def perform_create(self, serializer):
        try:
            serializer.save(patient=self.request.user)
        except Exception as e:
            logger.error(f"Error in ConsultationViewSet.perform_create: {str(e)}")
            raise

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in ConsultationViewSet.list: {str(e)}")
            return Response(
                {"detail": "An error occurred while fetching consultations."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update consultation status and/or type"""
        try:
            consultation = self.get_object()
            
            # Get data from request
            new_status = request.data.get('status')
            notes = request.data.get('notes')
            additional_data = request.data.get('additional_data', {})
            
            # Update consultation type if provided in additional_data
            if additional_data and 'consultation_type' in additional_data:
                old_type = consultation.consultation_type
                new_type = additional_data.get('consultation_type')
                logger.info(f"Changing consultation type from {old_type} to {new_type}")
                consultation.consultation_type = new_type
            
            # Update status if provided
            if new_status:
                consultation.status = new_status
            
            # Update notes if provided
            if notes:
                consultation.notes = notes
            
            # Save changes
            consultation.save()
            
            # Create notification for the patient based on status change
            if new_status:
                message = f"Your consultation status has been updated to {new_status}."
                if new_status == 'completed':
                    message = "Your consultation has been completed. Please check the recommendations."
                elif new_status == 'accepted':
                    doctor_name = f"Dr. {consultation.doctor.get_full_name()}" if consultation.doctor.get_full_name() else "your doctor"
                    message = f"Your consultation has been accepted by {doctor_name}."
                elif new_status == 'cancelled':
                    message = "Your consultation has been cancelled."
                    
                Notification.objects.create(
                    user=consultation.patient,
                    title=f'Consultation {new_status.capitalize()}',
                    message=message,
                    notification_type='consultation'
                )
            
            serializer = self.get_serializer(consultation)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in ConsultationViewSet.update_status: {str(e)}")
            return Response(
                {"detail": f"An error occurred while updating the consultation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete a consultation and optionally schedule a follow-up"""
        try:
            consultation = self.get_object()
            
            if consultation.status == 'completed':
                return Response(
                    {'error': 'Consultation is already completed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update consultation status and completion time
            consultation.status = 'completed'
            consultation.completed_at = timezone.now()
            
            # Handle follow-up if requested
            follow_up = request.data.get('follow_up', False)
            if follow_up:
                consultation.follow_up_required = True
                follow_up_date = request.data.get('follow_up_date')
                if follow_up_date:
                    consultation.follow_up_date = follow_up_date
            
            # Save updates
            consultation.save()
            
            # Create notification for the patient
            Notification.objects.create(
                user=consultation.patient,
                title='Consultation Completed',
                message='Your consultation has been completed. Please check the recommendations and prescription.',
                notification_type='consultation'
            )
            
            serializer = self.get_serializer(consultation)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in ConsultationViewSet.complete: {str(e)}")
            return Response(
                {"detail": "An error occurred while completing the consultation."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a consultation"""
        try:
            consultation = self.get_object()
            
            if consultation.status in ['completed', 'cancelled']:
                return Response(
                    {'error': f'Consultation is already {consultation.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            consultation.status = 'cancelled'
            consultation.save()
            
            # Create notification for the patient
            Notification.objects.create(
                user=consultation.patient,
                title='Consultation Cancelled',
                message='Your consultation has been cancelled.',
                notification_type='consultation'
            )
            
            serializer = self.get_serializer(consultation)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in ConsultationViewSet.cancel: {str(e)}")
            return Response(
                {"detail": "An error occurred while cancelling the consultation."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept a consultation"""
        try:
            consultation = self.get_object()
            
            if consultation.status != 'pending':
                return Response(
                    {'error': f'Consultation is already {consultation.status} and cannot be accepted'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update status and consultation type
            consultation.status = 'accepted'
            
            # Always set consultation type to follow_up when accepting
            if request.data.get('update_type', False) or consultation.consultation_type == 'initial':
                # Silently update the type without adding any system message to notes
                logger.info(f"Changing consultation type from {consultation.consultation_type} to follow_up")
                consultation.consultation_type = 'follow_up'
            
            # Handle any additional data - explicitly exclude notes to prevent system messages
            for field, value in request.data.items():
                if hasattr(consultation, field) and field not in ['status', 'notes']:  # Don't override status or notes
                    setattr(consultation, field, value)
            
            # Only update notes if explicitly provided and not empty
            if 'notes' in request.data and request.data['notes']:
                consultation.notes = request.data['notes']
                    
            consultation.save()
            
            # Create notification for the patient
            doctor_name = f"Dr. {consultation.doctor.get_full_name()}" if consultation.doctor.get_full_name() else "your doctor"
            Notification.objects.create(
                user=consultation.patient,
                title='Consultation Accepted',
                message=f'Your consultation request has been accepted by {doctor_name}. You will be contacted for further details.',
                notification_type='consultation'
            )
            
            serializer = self.get_serializer(consultation)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in ConsultationViewSet.accept: {str(e)}")
            return Response(
                {"detail": "An error occurred while accepting the consultation."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming consultations"""
        try:
            now = timezone.now()
            upcoming = self.get_queryset().filter(
                status='pending'
            ).order_by('created_at')
            
            serializer = self.get_serializer(upcoming, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in ConsultationViewSet.upcoming: {str(e)}")
            return Response(
                {"detail": "An error occurred while fetching upcoming consultations."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        """Handle update of consultation, ensuring proper type changes"""
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            
            # Check for special case: converting to follow_up
            if request.data.get('update_type', False) and 'consultation_type' in request.data:
                old_type = instance.consultation_type
                new_type = request.data.get('consultation_type')
                logger.info(f"Requested type change from {old_type} to {new_type}")
                
                # Make sure frontend_status is processed correctly
                if request.data.get('frontend_status') == 'accepted' and instance.status == 'pending':
                    instance.status = 'accepted'
                    logger.info(f"Setting status to accepted based on frontend_status")
            
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            if getattr(instance, '_prefetched_objects_cache', None):
                # If 'prefetch_related' has been applied to a queryset, we need to
                # forcibly invalidate the prefetch cache on the instance.
                instance._prefetched_objects_cache = {}

            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in ConsultationViewSet.update: {str(e)}")
            return Response(
                {"detail": "An error occurred while updating the consultation."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='admin')
    def admin_create(self, request):
        """Admin endpoint to create a consultation for any user"""
        # Check if user is admin
        if not request.user.is_staff and getattr(request.user, 'role', '') != 'admin':
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Get patient ID from request data
        patient_id = request.data.get('patient')
        if not patient_id:
            return Response(
                {"detail": "Patient ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            patient = User.objects.get(id=patient_id)
            
            # Get doctor ID from request data
            doctor_id = request.data.get('doctor')
            if not doctor_id:
                return Response(
                    {"detail": "Doctor ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                doctor = User.objects.get(id=doctor_id)
                
                serializer = AdminConsultationSerializer(data=request.data)
                if serializer.is_valid():
                    # Save with specified patient and doctor
                    serializer.save(patient=patient, doctor=doctor)
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
            except User.DoesNotExist:
                return Response(
                    {"detail": f"Doctor with ID {doctor_id} does not exist"},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except User.DoesNotExist:
            return Response(
                {"detail": f"Patient with ID {patient_id} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error in ConsultationViewSet.admin_create: {str(e)}")
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ScanViewSet(viewsets.ModelViewSet):
    queryset = Scan.objects.all()
    serializer_class = ScanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Allow users to see their own scans, doctors to see their patients' scans
        if self.request.user.role == 'doctor':
            # Doctors can see scans from their consultations
            return Scan.objects.filter(
                Q(user=self.request.user) |
                Q(consultations__doctor=self.request.user)
            ).distinct()
        elif self.request.user.role in ['assistant', 'admin'] or self.request.user.is_staff:
            # Assistants and admins can see all scans
            return Scan.objects.all()
        else:
            # Regular users see their own scans
            return Scan.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='suggest-consultation')
    def suggest_consultation(self, request, pk=None):
        """
        Endpoint to get available doctors and time slots for consultation based on scan results
        """
        scan = self.get_object()
        
        if not scan.requires_consultation:
            return Response({
                'error': 'This scan does not require consultation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get available doctors (users with doctor role)
        available_doctors = User.objects.filter(role='doctor')
        
        # Get the next 7 days of possible appointments
        today = timezone.now().date()
        available_dates = [(today + timedelta(days=i)).isoformat() for i in range(1, 8)]
        
        # Format doctor data with more details
        doctor_data = []
        for doctor in available_doctors:
            # Get total consultations count for each doctor
            consultation_count = Consultation.objects.filter(doctor=doctor).count()
            
            doctor_data.append({
                'id': doctor.id,
                'name': f"Dr. {doctor.get_full_name()}",
                'specialization': getattr(doctor, 'specialization', 'General'),
                'experience': consultation_count,  # Use consultation count as a measure of experience
                'profile_picture': doctor.profile.profile_picture.url if doctor.profile.profile_picture else None,
            })
        
        return Response({
            'scan_id': scan.id,
            'doctors': doctor_data,
            'available_dates': available_dates,
            'message': 'Please select a doctor and preferred date for your consultation'
        })

    @action(detail=True, methods=['post'], url_path='create-consultation')
    def create_consultation(self, request, pk=None):
        """
        Create an appointment and consultation based on scan results
        """
        scan = self.get_object()
        
        # Allow creating consultation even if not marked as required
        # if not scan.requires_consultation:
        #     return Response({
        #         'error': 'This scan does not require consultation'
        #     }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate request data
        doctor_id = request.data.get('doctor_id')
        appointment_date = request.data.get('date')
        appointment_time = request.data.get('time')
        
        if not all([doctor_id, appointment_date, appointment_time]):
            return Response({
                'error': 'Please provide doctor_id, date, and time'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            doctor = User.objects.get(id=doctor_id, role='doctor')
        except User.DoesNotExist:
            return Response({
                'error': 'Selected doctor not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create appointment
        try:
            date_time_str = f"{appointment_date} {appointment_time}"
            appointment_datetime = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M")
            
            # Check if the time slot is available
            if Appointment.objects.filter(
                date_time=appointment_datetime,
                status__in=['pending', 'confirmed']
            ).exists():
                return Response({
                    'error': 'This time slot is already taken. Please choose another time.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            appointment = Appointment.objects.create(
                user=scan.user,
                date_time=appointment_datetime,
                status='confirmed',
                notes=f"Consultation for scan #{scan.id}"
            )
            
            # Create consultation
            consultation = Consultation.objects.create(
                patient=scan.user,
                doctor=doctor,
                consultation_type='initial',
                status='pending'
            )
            
            # Create notifications for both user and doctor
            Notification.objects.create(
                user=scan.user,
                title='Consultation Scheduled',
                message=f'Your consultation with Dr. {doctor.get_full_name()} has been scheduled for {appointment_datetime.strftime("%B %d, %Y at %I:%M %p")}',
                notification_type='appointment'
            )
            
            Notification.objects.create(
                user=doctor,
                title='New Consultation Scheduled',
                message=f'A consultation has been scheduled with {scan.user.get_full_name()} for {appointment_datetime.strftime("%B %d, %Y at %I:%M %p")}',
                notification_type='appointment'
            )
            
            return Response({
                'message': 'Consultation scheduled successfully',
                'appointment_id': appointment.id,
                'consultation_id': consultation.id,
                'doctor_name': doctor.get_full_name(),
                'appointment_time': appointment_datetime.strftime("%B %d, %Y at %I:%M %p")
            })
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all().order_by('-date_time')
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AppointmentFilter

    def get_queryset(self):
        user = self.request.user
        # Allow admin and assistant roles to see all appointments
        if user.is_staff or getattr(user, 'role', None) in ['assistant', 'admin']:
            return self.queryset
        # Regular users can only see their own appointments
        return self.queryset.filter(user=user)

    @action(detail=False, methods=['get'])
    def assistant_appointments(self, request):
        """
        Get all appointments for assistants
        """
        if not request.user.is_staff and not getattr(request.user, 'role', None) == 'assistant':
            return Response(
                {'error': 'Only admin and assistants can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get active appointments (not deleted)
        appointments = self.get_queryset().exclude(status='deleted')
        serializer = self.get_serializer(appointments, many=True)
        return Response(serializer.data)

    def create_notification(self, appointment, action):
        """Create a notification for appointment status changes"""
        status_messages = {
            'confirmed': 'Your appointment has been confirmed',
            'cancelled': 'Your appointment has been cancelled',
            'completed': 'Your appointment has been marked as completed',
            'rescheduled': 'Your appointment has been rescheduled'
        }
        
        title = f"Appointment {action.title()}"
        message = status_messages.get(action, f"Your appointment status has been updated to {action}")
        
        Notification.objects.create(
            user=appointment.user,
            title=title,
            message=message,
            notification_type='appointment'
        )

    @action(detail=False, methods=['get'], url_path='check-upcoming')
    def check_upcoming(self, request):
        """
        Check for upcoming appointments for the current user
        """
        try:
            now = timezone.now()
            upcoming = self.get_queryset().filter(
                date_time__gt=now,
                status__in=['pending', 'confirmed']
            ).order_by('date_time')[:5]
            
            serializer = self.get_serializer(upcoming, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error checking upcoming appointments: {str(e)}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel an appointment
        """
        try:
            appointment = self.get_object()
            
            # Check if the appointment belongs to the user or if user is admin/assistant
            if not (appointment.user == request.user or request.user.is_staff or request.user.role == 'assistant'):
                return Response(
                    {'error': 'You do not have permission to cancel this appointment'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if the appointment is already cancelled or completed
            if appointment.status in ['cancelled', 'completed']:
                return Response(
                    {'error': f'Appointment is already {appointment.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update the appointment status to cancelled
            appointment.status = 'cancelled'
            appointment.save()
            
            # Create notification for cancellation
            self.create_notification(appointment, 'cancelled')
            
            serializer = self.get_serializer(appointment)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error cancelling appointment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        """
        Reschedule an appointment
        """
        try:
            appointment = self.get_object()
            
            # Check if the appointment belongs to the user or if user is admin/assistant
            if not (appointment.user == request.user or request.user.is_staff or request.user.role == 'assistant'):
                return Response(
                    {'error': 'You do not have permission to reschedule this appointment'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if the appointment is already cancelled or completed
            if appointment.status in ['cancelled', 'completed']:
                return Response(
                    {'error': f'Cannot reschedule an appointment that is {appointment.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get new date_time from request data
            date_time = request.data.get('date_time')
            if not date_time:
                return Response(
                    {'error': 'New date and time are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if the new time slot is available
            try:
                new_datetime = parse_datetime(date_time)
                if not timezone.is_aware(new_datetime):
                    new_datetime = timezone.make_aware(new_datetime)
                
                # Check if this appointment conflicts with any other
                if Appointment.objects.filter(
                    date_time=new_datetime,
                    status__in=['pending', 'confirmed']
                ).exclude(id=appointment.id).exists():
                    return Response(
                        {'error': 'This time slot is already taken'},
                        status=status.HTTP_409_CONFLICT
                    )
                
                # Update the appointment
                appointment.date_time = new_datetime
                appointment.save()
                
                # Create notification
                self.create_notification(appointment, 'rescheduled')
                
                serializer = self.get_serializer(appointment)
                return Response(serializer.data, status=status.HTTP_200_OK)
                
            except (ValueError, TypeError) as e:
                return Response(
                    {'error': f'Invalid date format: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except Exception as e:
            logger.error(f"Error rescheduling appointment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    @action(detail=True, methods=['post'])
    def completed(self, request, pk=None):
        """
        Mark an appointment as completed
        """
        try:
            appointment = self.get_object()
            
            # Check if user has permission (admin or assistant)
            if not (request.user.is_staff or request.user.role == 'assistant'):
                return Response(
                    {'error': 'Only admin or assistant users can mark appointments as completed'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if the appointment is already completed or cancelled
            if appointment.status in ['completed', 'cancelled']:
                return Response(
                    {'error': f'Appointment is already {appointment.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update the appointment status
            appointment.status = 'completed'
            appointment.save()
            
            # Create notification
            self.create_notification(appointment, 'completed')
            
            serializer = self.get_serializer(appointment)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error completing appointment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def confirmed(self, request, pk=None):
        """
        Mark an appointment as confirmed
        """
        try:
            appointment = self.get_object()
            
            # Check if user has permission (admin or assistant)
            if not (request.user.is_staff or request.user.role == 'assistant'):
                return Response(
                    {'error': 'Only admin or assistant users can confirm appointments'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if the appointment is already confirmed, completed or cancelled
            if appointment.status in ['confirmed', 'completed', 'cancelled']:
                return Response(
                    {'error': f'Appointment is already {appointment.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update the appointment status
            appointment.status = 'confirmed'
            appointment.save()
            
            # Create notification
            self.create_notification(appointment, 'confirmed')
            
            serializer = self.get_serializer(appointment)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error confirming appointment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def perform_create(self, serializer):
        # Check for appointment conflicts
        date_time = serializer.validated_data.get('date_time')
        
        # Ensure date_time is in UTC
        try:
            if date_time and not timezone.is_aware(date_time):
                date_time = timezone.make_aware(date_time, pytz.UTC)
        except Exception as e:
            logger.error(f"Error making date_time timezone aware: {str(e)}")
            # Try a more basic approach as fallback
            if date_time and not timezone.is_aware(date_time):
                try:
                    date_time = timezone.make_aware(date_time)
                except Exception:
                    # Continue with original date_time if all else fails
                    pass
            
        if Appointment.objects.filter(
            date_time=date_time,
            status__in=['pending', 'confirmed']
        ).exists():
            raise AppointmentConflictException()
        
        # Check if this is an admin-created appointment
        admin_created = self.request.data.get('admin_created', False)
        
        # If admin is creating it for someone else
        if admin_created and (self.request.user.is_staff or self.request.user.role == 'admin'):
            # Get the target user ID from the request data
            user_id = self.request.data.get('user')
            if user_id:
                try:
                    target_user = User.objects.get(id=user_id)
                    # Save with the target user, not the admin user
                    serializer.save(user=target_user)
                    return
                except User.DoesNotExist:
                    # If user doesn't exist, fall back to default behavior
                    pass
        
        # Default behavior: save with the current user
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        new_status = serializer.validated_data.get('status')
        old_status = instance.status
        
        # Allow admin or assistant to change status to confirmed or completed
        if new_status in ['confirmed', 'completed'] and not (self.request.user.is_staff or self.request.user.role == 'assistant'):
            raise PermissionDenied("Only admin or assistant users can confirm or complete appointments")
        
        # Save the updated appointment
        updated_appointment = serializer.save()
        
        # Create notification if status has changed
        if new_status != old_status:
            self.create_notification(updated_appointment, new_status)
        
        # If date_time has changed, create a rescheduled notification
        if 'date_time' in serializer.validated_data and serializer.validated_data['date_time'] != instance.date_time:
            self.create_notification(updated_appointment, 'rescheduled')

    @action(detail=False, methods=['get'], url_path='taken-slots', url_name='taken-slots')
    def taken_slots(self, request):
        """
        Get all taken time slots for a specific date.
        Query parameter: date (YYYY-MM-DD)
        """
        from datetime import datetime, time
        
        date = request.query_params.get('date')
        if not date:
            return Response(
                {'error': 'Date parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Parse the date string to datetime object
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            
            # Simplify the approach to avoid timezone issues
            # Get all appointments for the specified date using date__exact
            appointments = Appointment.objects.filter(
                date_time__date=date_obj,
                status__in=['pending', 'confirmed']  # Only consider active appointments
            )
            
            # Extract the time slots from the appointments without timezone manipulation
            taken_slots = []
            for appointment in appointments:
                # Return time in 24-hour format (HH:MM) for consistent comparison with frontend
                time_str = appointment.date_time.strftime('%H:%M')
                taken_slots.append(time_str)
            
            return Response({'taken_slots': taken_slots})
            
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import traceback
            print(f"Error in taken_slots: {str(e)}")
            print(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='admin')
    def admin_create(self, request):
        """
        Admin endpoint for creating appointments for any user.
        Only accessible to admin users.
        """
        # Check if user has admin privileges
        if not request.user.is_staff and getattr(request.user, 'role', '') != 'admin':
            return Response(
                {'error': 'Only admin users can create appointments for other users'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        try:
            # Extract user ID from request data
            user_id = request.data.get('user')
            if not user_id:
                return Response(
                    {'error': 'User ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Verify user exists
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': f'User with ID {user_id} does not exist'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Create serializer with data from request
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                # Save with explicit user instead of request.user
                serializer.save(user=user)
                
                # Create notification for the user
                Notification.objects.create(
                    user=user,
                    title="New Appointment Scheduled",
                    message=f"An appointment has been scheduled for you on {serializer.validated_data['date_time'].strftime('%Y-%m-%d at %H:%M')}",
                    notification_type='appointment'
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error in admin_create appointment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        
    @action(detail=False, methods=['post'], url_path='admin')
    def admin_create(self, request):
        """Admin endpoint to create a payment for any user"""
        # Check if user is admin
        if not request.user.is_staff and getattr(request.user, 'role', '') != 'admin':
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = AdminPaymentSerializer(data=request.data)
        if serializer.is_valid():
            # Get user ID from request data
            user_id = request.data.get('user')
            if not user_id:
                return Response(
                    {"detail": "User ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                user = User.objects.get(id=user_id)
                serializer.save(user=user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except User.DoesNotExist:
                return Response(
                    {"detail": f"User with ID {user_id} does not exist"},
                    status=status.HTTP_404_NOT_FOUND
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def email_token_auth(request):
    """
    Authenticate user with email and token.
    """
    try:
        email = request.data.get('email')
        token = request.data.get('token')
        
        if not email or not token:
            return Response(
                {'error': 'Email and token are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        User = get_user_model()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify token
        try:
            token_obj = Token.objects.get(user=user, key=token)
        except Token.DoesNotExist:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        return Response({
            'token': token_obj.key,
            'user_id': user.id,
            'email': user.email,
            'username': user.username
        })
        
    except Exception as e:
        logger.error(f"Error in email token auth: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        """
        Create a notification with proper error handling
        """
        try:
            logger.info(f"Creating notification with data: {request.data}")
            serializer = self.get_serializer(data=request.data, context={'request': request})
            
            if serializer.is_valid():
                self.perform_create(serializer)
                logger.info("Notification created successfully")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"Notification validation errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Error creating notification: {str(e)}")
            return Response(
                {"detail": f"Error creating notification: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        notifications = self.get_queryset()
        notifications.update(is_read=True)
        return Response({'status': 'success'})
    
    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        try:
            notification = self.get_queryset().get(pk=pk)
            notification.is_read = True
            notification.save()
            return Response({'status': 'success'})
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def predict_scan(request):
    try:
        # Get the file from the request - try both 'file' and 'image' field names
        file = request.FILES.get('file') or request.FILES.get('image')
        if not file:
            return Response(
                {'error': 'No file provided. Please provide a file with either "file" or "image" field name.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use our ML service to analyze the X-ray
        result = ml_service.analyze_xray(file)
        
        # Check if analysis was successful
        if result['success']:
            # Get the Scan model if it exists
            scan_id = request.data.get('scan_id')
            if scan_id:
                try:
                    scan = Scan.objects.get(id=scan_id, user=request.user)
                    
                    # Update the scan with ML results
                    scan.status = 'completed'
                    scan.result = f"Diagnosis: {result['diagnosis']} with {result['confidence']}% confidence"
                    
                    # Set result_status based on diagnosis
                    if result['diagnosis'] == 'Normal':
                        scan.result_status = 'healthy'
                        scan.requires_consultation = False
                    elif result['diagnosis'] == 'Pneumonia':
                        scan.result_status = 'requires_consultation'
                        scan.requires_consultation = True
                    else:  # Lung_Opacity
                        scan.result_status = 'optional_consultation'
                        scan.requires_consultation = True
                    
                    # Save confidence score
                    scan.confidence_score = result['confidence']
                    scan.save()
                    
                    # Include scan info in response
                    result['scan_updated'] = True
                    result['scan_id'] = scan.id
                    
                except Scan.DoesNotExist:
                    # Scan not found but continue with prediction
                    result['scan_updated'] = False
            
            return Response(result)
        else:
            # ML service error
            logger.error(f"ML service error: {result['error']}")
            return Response(
                {'error': 'ML service error', 'details': result['error']},
                status=result.get('status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
            )
                
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        return Response(
            {'error': f'Error processing request: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def predict_view(request):
    if request.method == 'POST' and request.FILES.get('xray'):
        try:
            # Get uploaded file
            uploaded_file = request.FILES['xray']
            
            # Print file details for debugging
            print(f"File name: {uploaded_file.name}")
            print(f"File size: {uploaded_file.size} bytes")
            print(f"Content type: {uploaded_file.content_type}")
            
            # Ensure the content type is one of the accepted types
            if uploaded_file.content_type not in ["image/jpeg", "image/png", "image/jpg"]:
                # Default to image/jpeg if the browser doesn't provide the correct content type
                if uploaded_file.name.lower().endswith(('.jpg', '.jpeg')):
                    content_type = "image/jpeg"
                elif uploaded_file.name.lower().endswith('.png'):
                    content_type = "image/png"
                else:
                    return render(request, 'error.html', {
                        'error': f"Unsupported file type: {uploaded_file.content_type}. Only JPEG, JPG, and PNG are supported."
                    })
            else:
                content_type = uploaded_file.content_type
            
            # Use our ML service to analyze the X-ray
            result = ml_service.analyze_xray(uploaded_file)
            
            # Check if analysis was successful
            if result['success']:
                # Debug output
                print(f"ML API Response: {result}")
                
                # Extract results
                diagnosis = result['diagnosis']
                confidence = result['confidence']
                
                return render(request, 'result.html', {
                    'result': diagnosis,
                    'probability': f"{confidence:.2f}%",  # Format confidence as percentage
                    'details': result.get('details', {})
                })
            else:
                # ML service error
                error_msg = result.get('error', 'Unknown error')
                print(f"ML API error: {error_msg}")
                return render(request, 'error.html', {'error': error_msg})

        except Exception as e:
            error_message = str(e)
            print(f"Error in predict_view: {error_message}")
            return render(request, 'error.html', {'error': error_message})
    
    return render(request, 'upload.html')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_consultation(request, appointment_id):
    try:
        appointment = Appointment.objects.get(id=appointment_id)
        
        # Check if consultation already exists
        if hasattr(appointment, 'consultation'):
            return Response(
                {'error': 'Consultation already exists for this appointment'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create consultation without appointment reference
        consultation = Consultation.objects.create(
            patient=appointment.user,
            doctor=User.objects.get(id=request.data.get('doctor_id')),
            scan=appointment.scan if hasattr(appointment, 'scan') else None,
            consultation_type=request.data.get('consultation_type', 'regular'),
            status='pending',
            notes=request.data.get('notes', '')
        )

        # Create a separate Consultation record (not linked to appointment)
        Consultation.objects.create(
            appointment=appointment,
            patient=appointment.user,
            doctor=User.objects.get(id=request.data.get('doctor_id')),
            consultation_type=request.data.get('consultation_type', 'initial'),
            status='pending',
            notes=request.data.get('notes', '')
        )

        serializer = ConsultationSerializer(consultation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Appointment.DoesNotExist:
        return Response(
            {'error': 'Appointment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['specialty', 'gender', 'is_accepting_new_patients']
    search_fields = ['user__first_name', 'user__last_name', 'specialty', 'bio', 'education', 'languages']
    
    def get_queryset(self):
        # Return all doctors for admin users
        if self.request.user.is_staff or self.request.user.role == 'admin':
            return Doctor.objects.all()
        
        # Return only active doctors for other users
        return Doctor.objects.filter(user__is_active=True)
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get all available doctors for consultation"""
        doctors = self.get_queryset().filter(user__is_active=True)
        
        # Add filtering by specialty
        specialty = request.query_params.get('specialty', None)
        if specialty:
            doctors = doctors.filter(specialty=specialty)
            
        # Add filtering by years of experience
        min_experience = request.query_params.get('min_experience', None)
        if min_experience and min_experience.isdigit():
            doctors = doctors.filter(years_of_experience__gte=int(min_experience))
            
        # Add filtering by gender
        gender = request.query_params.get('gender', None)
        if gender:
            doctors = doctors.filter(gender=gender)
            
        # Add filtering by language
        language = request.query_params.get('language', None)
        if language:
            doctors = doctors.filter(languages__icontains=language)
            
        # Add filtering for accepting new patients
        accepting_patients = request.query_params.get('accepting_new_patients', None)
        if accepting_patients is not None:
            is_accepting = accepting_patients.lower() == 'true'
            doctors = doctors.filter(is_accepting_new_patients=is_accepting)
        
        serializer = self.get_serializer(doctors, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        """Get doctor's available schedule"""
        doctor = self.get_object()
        return Response({
            'available_days': doctor.available_days,
            'available_hours': doctor.available_hours
        })
    
    @action(detail=True, methods=['post'])
    def update_schedule(self, request, pk=None):
        """Update doctor's schedule"""
        if request.user.role != 'doctor' or request.user.doctor_profile.id != int(pk):
            return Response(
                {'error': 'Only the doctor can update their schedule'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        doctor = self.get_object()
        available_days = request.data.get('available_days')
        available_hours = request.data.get('available_hours')
        
        if available_days is not None:
            doctor.available_days = available_days
        if available_hours is not None:
            doctor.available_hours = available_hours
        
        doctor.save()
        return Response(self.get_serializer(doctor).data)
        
    @action(detail=False, methods=['get'])
    def specialties(self, request):
        """Get list of all specialties with count of doctors"""
        specialties = {}
        for choice in Doctor.SPECIALTY_CHOICES:
            specialty_code = choice[0]
            specialty_name = choice[1]
            count = Doctor.objects.filter(specialty=specialty_code, user__is_active=True).count()
            specialties[specialty_code] = {
                'name': specialty_name,
                'count': count
            }
        return Response(specialties)
        
    @action(detail=True, methods=['get'])
    def consultations(self, request, pk=None):
        """Get consultation history for a doctor"""
        doctor = self.get_object()
        
        # Only the doctor or admins can access this endpoint
        if not (request.user.id == doctor.user.id or request.user.is_staff or request.user.role == 'admin'):
            return Response(
                {'error': 'You do not have permission to view this doctor\'s consultations'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        consultations = Consultation.objects.filter(doctor=doctor.user).order_by('-created_at')
        serializer = ConsultationSerializer(consultations, many=True)
        return Response(serializer.data)
        
    @action(detail=True, methods=['post'])
    def toggle_accepting_patients(self, request, pk=None):
        """Toggle whether doctor is accepting new patients"""
        doctor = self.get_object()
        
        # Only the doctor or admins can toggle this
        if not (request.user.id == doctor.user.id or request.user.is_staff or request.user.role == 'admin'):
            return Response(
                {'error': 'You do not have permission to change this setting'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        doctor.is_accepting_new_patients = not doctor.is_accepting_new_patients
        doctor.save()
        
        return Response({
            'is_accepting_new_patients': doctor.is_accepting_new_patients
        })

class AssistantViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['username', 'first_name', 'last_name', 'email']
    
    def get_queryset(self):
        return User.objects.filter(role='assistant', is_active=True)
    
    @action(detail=True, methods=['get'])
    def appointments(self, request, pk=None):
        """Get appointments for a specific assistant"""
        assistant = self.get_object()
        if assistant.role != 'assistant':
            return Response(
                {'error': 'This user is not an assistant'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        consultations = Consultation.objects.filter(
            Q(status='pending') | Q(status='confirmed')
        ).order_by('date_time')
        
        serializer = ConsultationSerializer(consultations, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_appointments(self, request):
        """Get appointments for the currently logged-in assistant"""
        if request.user.role != 'assistant':
            return Response(
                {'error': 'Only assistants can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        consultations = Consultation.objects.filter(
            Q(status='pending') | Q(status='confirmed')
        ).order_by('date_time')
        
        serializer = ConsultationSerializer(consultations, many=True)
        return Response(serializer.data)

# Add this new viewset after the existing ones
class XRayImageViewSet(viewsets.ModelViewSet):
    """
    API endpoints for accessing X-ray Images directly
    """
    serializer_class = XRayImageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        # Staff users (admin, assistant, doctor) can see all X-rays
        if user.is_staff or getattr(user, 'role', '') in ['admin', 'assistant', 'doctor']:
            return XRayImage.objects.all().order_by('-upload_date')
        # Regular users (patients) can only see their own X-rays
        else:
            return XRayImage.objects.filter(patient=user).order_by('-upload_date')
    
    def retrieve(self, request, pk=None):
        """Get a specific X-ray image"""
        try:
            xray = self.get_object()
            serializer = self.get_serializer(xray)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"detail": f"Error retrieving X-ray image: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request):
        """List X-ray images for the current user"""
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"detail": f"Error listing X-ray images: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request, *args, **kwargs):
        """Create a new X-ray image with better error handling"""
        try:
            # Log the received data for debugging
            logger = logging.getLogger(__name__)
            logger.info(f"Received X-ray upload request: {request.data}")
            
            # Ensure we have all required data
            if 'image' not in request.data:
                return Response(
                    {"detail": "No image file provided"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if 'appointment' not in request.data:
                return Response(
                    {"detail": "Appointment ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if 'patient' not in request.data:
                return Response(
                    {"detail": "Patient ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if 'assistant' not in request.data:
                return Response(
                    {"detail": "Assistant ID is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create the serializer with the request in context
            serializer = self.get_serializer(data=request.data, context={'request': request})
            
            # Validate the data
            if serializer.is_valid():
                self.perform_create(serializer)
                logger.info("X-ray image created successfully")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"X-ray serializer validation errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception(f"Error creating X-ray image: {str(e)}")
            return Response(
                {"detail": f"Error creating X-ray image: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CreatorViewSet(viewsets.ModelViewSet):
    """
    API endpoints for Creators/Team Members
    """
    queryset = Creator.objects.all()
    serializer_class = CreatorSerializer
    permission_classes = [AllowAny]  # Allow public access for viewing creators
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['user__first_name', 'user__last_name', 'job_title', 'role']
    
    def get_queryset(self):
        """
        This view should return only active creators by default
        """
        queryset = Creator.objects.all()
        
        # Filter by active status
        active = self.request.query_params.get('active')
        if active is not None:
            queryset = queryset.filter(is_active=(active.lower() == 'true'))
        else:
            # Default to active creators only
            queryset = queryset.filter(is_active=True)
            
        return queryset.select_related('user', 'user__profile')

    def get_permissions(self):
        """
        Custom permissions:
        - GET requests are allowed for everyone
        - All other methods require admin privileges
        """
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [AllowAny()]
        return [IsAuthenticated()]
        
    def perform_create(self, serializer):
        if not self.request.user.is_staff and self.request.user.role != 'admin':
            raise PermissionDenied("Only administrators can create team members")
        serializer.save()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def proxy_image(request):
    """
    Proxy for securely fetching images from HTTP sources to avoid mixed content errors
    """
    import requests
    from django.http import HttpResponse, FileResponse
    from io import BytesIO
    import mimetypes
    import urllib.parse

    # Get image URL from request parameters
    url = request.GET.get('url')
    if not url:
        return Response({'error': 'No URL provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Basic URL validation
    try:
        parsed_url = urllib.parse.urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return Response({'error': 'Invalid URL format'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': f'Invalid URL: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Fetch the image
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code != 200:
            return Response(
                {'error': f'Failed to fetch image, status code: {response.status_code}'}, 
                status=status.HTTP_502_BAD_GATEWAY
            )
        
        # Determine content type
        content_type = response.headers.get('Content-Type')
        if not content_type or not content_type.startswith('image/'):
            # Try to guess from URL if server didn't provide content type
            content_type, _ = mimetypes.guess_type(url)
            if not content_type or not content_type.startswith('image/'):
                content_type = 'image/jpeg'  # Default to JPEG
        
        # Create file-like object from image data
        image_data = BytesIO(response.content)
        
        # Return the image with proper content type
        response = FileResponse(image_data, content_type=content_type)
        
        # Add CORS headers to ensure the image can be loaded by the frontend
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        
        return response
        
    except Exception as e:
        return Response(
            {'error': f'Error proxying image: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
