from rest_framework.exceptions import APIException
from rest_framework import status

class InvalidRoleError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid role specified'
    default_code = 'invalid_role'

class InvalidSubscriptionError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid subscription type specified'
    default_code = 'invalid_subscription'

class FileUploadError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Error uploading file'
    default_code = 'file_upload_error'

class AppointmentConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Appointment time conflict'
    default_code = 'appointment_conflict'

class PaymentError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Payment processing error'
    default_code = 'payment_error'

class ScanProcessingError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Error processing scan'
    default_code = 'scan_processing_error'

class ResourceNotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Resource not found'
    default_code = 'resource_not_found'

class PermissionDeniedError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Permission denied'
    default_code = 'permission_denied'

class ValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Validation error'
    default_code = 'validation_error'

class AuthenticationError(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Authentication failed'
    default_code = 'authentication_error' 