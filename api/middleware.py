from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.conf import settings
import time
import logging
import uuid

logger = logging.getLogger('api')

class RequestLoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        duration = time.time() - request.start_time
        logger.info(
            f"Method: {request.method} | "
            f"Path: {request.path} | "
            f"Status: {response.status_code} | "
            f"Duration: {duration:.2f}s"
        )
        return response

class ExceptionHandlingMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        logger.error(f"Exception occurred: {str(exception)}")
        return JsonResponse({
            'error': 'An unexpected error occurred',
            'message': str(exception)
        }, status=500)

class CORSHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Get allowed origins from settings
        origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', ["https://chopper-mu.vercel.app"])
        
        # Extract the origin from the request headers
        origin = request.headers.get('Origin', '')
        
        # Check if the origin is in our allowed list or we allow all origins
        if getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', True) or origin in origins:
            # Set the specific origin instead of a wildcard for credentials support
            response['Access-Control-Allow-Origin'] = origin or '*'
        else:
            # If not in allowed origins, set the first allowed origin as default
            response['Access-Control-Allow-Origin'] = origins[0] if origins else '*'
            
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, X-CSRFToken'
        response['Access-Control-Allow-Credentials'] = 'true'
        
        return response

class TokenValidationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # List of endpoints that don't require authentication
        public_paths = [
            '/api/users/register/',
            '/api/auth/token/',
            '/api/auth/email-token/',
        ]
        
        # Skip validation for non-API paths
        if not request.path.startswith('/api/'):
            return None
            
        # Skip validation for public endpoints
        if any(request.path.startswith(path) for path in public_paths):
            return None
            
        # Skip validation for OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return None

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        # If no authorization header is provided for protected endpoints
        if not auth_header:
            return JsonResponse({
                'error': 'Authentication required',
                'detail': 'Authentication credentials were not provided.'
            }, status=401)
            
        # If authorization header is provided, validate the token
        if not auth_header.startswith('Token '):
            return JsonResponse({
                'error': 'Invalid authorization header',
                'detail': 'Authorization header must start with Token'
            }, status=401)
            
        token = auth_header.split(' ')[1]
        if not token:
            return JsonResponse({
                'error': 'Invalid token',
                'detail': 'Token is invalid or expired'
            }, status=401)
            
        return None

class RateLimitMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/api/'):
            # Implement rate limiting logic here
            pass
        return None

class RequestIDMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.request_id = str(uuid.uuid4())
        return None
    
    def process_response(self, request, response):
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        return response

class SecurityHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

class CorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Get allowed origins from settings
        origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', ["https://chopper-mu.vercel.app"])
        
        # Extract the origin from the request headers
        origin = request.headers.get('Origin', '')
        
        # Check if the origin is in our allowed list or we allow all origins
        if getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', True) or origin in origins:
            # Set the specific origin instead of a wildcard for credentials support
            response["Access-Control-Allow-Origin"] = origin or '*'
        else:
            # If not in allowed origins, set the first allowed origin as default
            response["Access-Control-Allow-Origin"] = origins[0] if origins else '*'
            
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, X-CSRFToken"
        response["Access-Control-Allow-Credentials"] = "true"
        
        return response 