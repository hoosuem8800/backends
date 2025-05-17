from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserProfile, Scan, Appointment, Payment, Consultation, Doctor, Notification, XRayImage, Creator
import logging
from django.utils import timezone
import pytz

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    phone_number = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'subscription_type', 'phone_number']
        read_only_fields = ['id']
    
    def get_phone_number(self, obj):
        if hasattr(obj, 'profile') and obj.profile:
            return obj.profile.phone_number
        return None

class UserProfileSerializer(serializers.ModelSerializer):
    # Add nested user serializer to include user data
    user_data = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'user_data', 'phone_number', 'address', 'profile_picture']
        read_only_fields = ['id', 'user']
    
    def get_user_data(self, obj):
        # Return serialized user data
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'email': obj.user.email,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
            'role': obj.user.role
        }

class ConsultationSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    scan_details = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = [
            'id', 'patient', 'patient_name', 'doctor', 'doctor_name',
            'scan', 'scan_details', 'consultation_type', 'status', 
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_patient_name(self, obj):
        return obj.patient.get_full_name()

    def get_doctor_name(self, obj):
        return obj.doctor.get_full_name()

    def get_scan_details(self, obj):
        if obj.scan:
            return {
                'id': obj.scan.id,
                'upload_date': obj.scan.upload_date,
                'status': obj.scan.status,
                'result': obj.scan.result,
                'confidence_score': obj.scan.confidence_score,
                'requires_consultation': obj.scan.requires_consultation
            }
        return None

class AdminConsultationSerializer(serializers.ModelSerializer):
    """Consultation serializer for admin use that allows setting the patient field"""
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    scan_details = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = [
            'id', 'patient', 'patient_name', 'doctor', 'doctor_name',
            'scan', 'scan_details', 'consultation_type', 'status', 
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_patient_name(self, obj):
        return obj.patient.get_full_name()

    def get_doctor_name(self, obj):
        return obj.doctor.get_full_name()

    def get_scan_details(self, obj):
        if obj.scan:
            return {
                'id': obj.scan.id,
                'upload_date': obj.scan.upload_date,
                'status': obj.scan.status,
                'result': obj.scan.result,
                'confidence_score': obj.scan.confidence_score,
                'requires_consultation': obj.scan.requires_consultation
            }
        return None

class ScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scan
        fields = ['id', 'user', 'image', 'upload_date', 'status', 'result', 'confidence_score', 'notes']
        read_only_fields = ['id', 'user', 'upload_date']

class AppointmentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Appointment
        fields = ['id', 'user', 'date_time', 'status', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_status(self, value):
        valid_statuses = dict(Appointment.STATUS_CHOICES).keys()
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return value
        
    def validate_date_time(self, value):
        """
        Preserve the datetime exactly as provided without timezone handling.
        This prevents timezone conversion issues on different platforms.
        """
        if value and hasattr(value, 'tzinfo') and value.tzinfo:
            # Remove timezone info to store as naive datetime
            return value.replace(tzinfo=None)
        return value

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'user', 'amount', 'status', 'payment_method', 'transaction_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

class AdminPaymentSerializer(serializers.ModelSerializer):
    """Payment serializer for admin use that allows setting the user field"""
    class Meta:
        model = Payment
        fields = ['id', 'user', 'amount', 'status', 'payment_method', 'transaction_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    profile = serializers.DictField(required=False, write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'confirm_password', 'first_name', 'last_name', 'role', 'subscription_type', 'profile']
        extra_kwargs = {
            'password': {'write_only': True},
            'confirm_password': {'write_only': True}
        }
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        
        # Validate role
        if data['role'] not in dict(User.ROLE_CHOICES):
            raise serializers.ValidationError({'role': f"Invalid role. Must be one of: {', '.join(dict(User.ROLE_CHOICES).keys())}"})
        
        # Validate subscription_type
        if data['subscription_type'] not in dict(User.SUBSCRIPTION_CHOICES):
            raise serializers.ValidationError({'subscription_type': f"Invalid subscription type. Must be one of: {', '.join(dict(User.SUBSCRIPTION_CHOICES).keys())}"})
        
        return data
    
    def create(self, validated_data):
        logger = logging.getLogger(__name__)
        logger.info("Starting user creation in serializer")
        
        try:
            # Extract profile data and confirm_password
            profile_data = validated_data.pop('profile', {})
            validated_data.pop('confirm_password', None)
            
            logger.info(f"Creating user with data: {validated_data}")
            
            # Create user
            password = validated_data.pop('password')
            user = User(**validated_data)
            user.set_password(password)
            user.save()
            
            logger.info(f"User created successfully with ID: {user.id}")
            
            # Update profile if profile data was provided
            if profile_data:
                logger.info(f"Updating profile for user with data: {profile_data}")
                if hasattr(user, 'profile'):
                    profile = user.profile
                    for key, value in profile_data.items():
                        setattr(profile, key, value)
                    profile.save()
                    logger.info(f"Profile updated successfully")
            
            # Create Doctor profile if role is doctor
            if user.role == 'doctor':
                logger.info(f"Creating doctor profile for user with ID: {user.id}")
                try:
                    # Extract doctor data from profile data if it exists
                    doctor_data = profile_data.get('doctor', {})
                    
                    # Create a unique license number if not provided
                    license_number = doctor_data.get('license_number', f"TMP-{user.id}-{int(timezone.now().timestamp())}")
                    
                    # Create the doctor profile
                    Doctor.objects.create(
                        user=user,
                        license_number=license_number,
                        specialty=doctor_data.get('specialty', 'general'),
                        years_of_experience=doctor_data.get('years_of_experience', 0),
                        bio=doctor_data.get('bio', ''),
                        age=doctor_data.get('age', None),
                        gender=doctor_data.get('gender', None),
                        languages=doctor_data.get('languages', ''),
                        education=doctor_data.get('education', ''),
                        awards=doctor_data.get('awards', ''),
                        is_accepting_new_patients=doctor_data.get('is_accepting_new_patients', True)
                    )
                    logger.info(f"Doctor profile created successfully")
                except Exception as e:
                    logger.error(f"Error creating doctor profile: {str(e)}")
                    # We don't want to roll back the entire transaction for this
                    # The doctor profile can be created later
            
            return user
            
        except Exception as e:
            logger.error(f"Error in create method: {str(e)}")
            raise 

class DoctorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    specialty_display = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    gender_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Doctor
        fields = [
            'id', 'user', 'full_name', 'specialty', 'specialty_display',
            'years_of_experience', 'age', 'gender', 'gender_display',
            'license_number', 'profile_picture', 'profile_picture_url', 
            'bio', 'education', 'awards', 'languages',
            'consultation_fee', 'rating', 'total_consultations', 
            'available_days', 'available_hours', 'is_accepting_new_patients'
        ]
        read_only_fields = ['id', 'rating', 'total_consultations']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    
    def get_specialty_display(self, obj):
        return obj.get_specialty_display()
    
    def get_gender_display(self, obj):
        return obj.get_gender_display() if obj.gender else None
    
    def get_profile_picture_url(self, obj):
        if obj.profile_picture:
            return obj.profile_picture.url
        return None

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user', 'title', 'message', 'notification_type', 'is_read', 'created_at']
        read_only_fields = ['id', 'created_at']
        
    def create(self, validated_data):
        """
        Create a new notification, handling user_id from request data
        """
        request = self.context.get('request')
        
        # If user is not set but user_id is provided in request data,
        # fetch the user object and set it
        user = validated_data.get('user')
        if not user and request and 'user_id' in request.data:
            try:
                user_id = request.data.get('user_id')
                user = User.objects.get(id=user_id)
                validated_data['user'] = user
            except User.DoesNotExist:
                raise serializers.ValidationError({'user_id': f"User with id {request.data.get('user_id')} does not exist"})
                
        # If no user is set at this point and the requesting user is authenticated,
        # default to creating a notification for the requesting user
        if not validated_data.get('user') and request and request.user.is_authenticated:
            validated_data['user'] = request.user
            
        # If we still don't have a user, raise an error
        if not validated_data.get('user'):
            raise serializers.ValidationError({'user': "User field is required"})
            
        # Create the notification
        return super().create(validated_data)

class XRayImageSerializer(serializers.ModelSerializer):
    patient = UserSerializer(read_only=True)
    assistant = UserSerializer(read_only=True)
    
    class Meta:
        model = XRayImage
        fields = ['id', 'appointment', 'image', 'patient', 'assistant', 'upload_date', 'notes']
        read_only_fields = ['id', 'upload_date']
    
    def create(self, validated_data):
        """
        Create a new XRayImage with the parsed data from request
        """
        # Get patient and assistant IDs from the request data
        request = self.context.get('request')
        patient_id = request.data.get('patient')
        assistant_id = request.data.get('assistant')
        
        # Get the User model
        User = get_user_model()
        
        # Validate we have all required data
        if not patient_id:
            raise serializers.ValidationError({"patient": "Patient ID is required"})
        
        if not assistant_id:
            raise serializers.ValidationError({"assistant": "Assistant ID is required"})
        
        # Get the patient and assistant users
        try:
            patient = User.objects.get(id=patient_id)
            assistant = User.objects.get(id=assistant_id)
        except User.DoesNotExist:
            raise serializers.ValidationError({"error": "Patient or assistant user not found"})
        
        # Create the XRayImage instance
        xray_image = XRayImage.objects.create(
            patient=patient,
            assistant=assistant,
            **validated_data
        )
        
        return xray_image
    
    def update(self, instance, validated_data):
        """
        Update an existing XRayImage
        """
        # Update fields that can be changed
        instance.notes = validated_data.get('notes', instance.notes)
        
        # Only update image if a new one is provided
        if 'image' in validated_data:
            instance.image = validated_data.get('image')
        
        instance.save()
        return instance

class CreatorSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.profile.phone_number', read_only=True)
    profile_picture = serializers.SerializerMethodField()
    
    class Meta:
        model = Creator
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number', 
                  'job_title', 'role', 'contribution', 'is_active', 
                  'profile_picture', 'created_at', 'updated_at']
    
    def get_profile_picture(self, obj):
        request = self.context.get('request')
        if hasattr(obj.user, 'profile') and obj.user.profile.profile_picture:
            if request:
                return request.build_absolute_uri(obj.user.profile.profile_picture.url)
            return obj.user.profile.profile_picture.url
        return None 