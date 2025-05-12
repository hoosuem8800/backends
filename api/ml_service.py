import requests
import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)

class ChestXrayService:
    """Service to interact with the chest X-ray ML model API"""
    
    def __init__(self):
        # Get the ML API URL from environment variable or use the Railway deployment by default
        self.ml_api_url = os.environ.get('ML_API_URL', 'https://sage-production.up.railway.app')
        # Remove trailing slash if present
        self.ml_api_url = self.ml_api_url.rstrip('/')
        logger.info(f"ML API URL: {self.ml_api_url}")
    
    def check_health(self):
        """Check if the ML API is healthy"""
        try:
            response = requests.get(f"{self.ml_api_url}/health", timeout=10)
            return response.status_code == 200 and response.json().get('status') == 'healthy'
        except Exception as e:
            logger.error(f"Error checking ML API health: {str(e)}")
            return False
    
    def check_model_status(self):
        """Check if the ML model is loaded and ready"""
        try:
            response = requests.get(f"{self.ml_api_url}/model-status", timeout=10)
            if response.status_code == 200:
                status_data = response.json()
                return status_data.get('model_ready', False)
            return False
        except Exception as e:
            logger.error(f"Error checking ML model status: {str(e)}")
            return False
    
    def analyze_xray(self, image_file):
        """
        Send X-ray image to ML API for analysis
        
        Args:
            image_file: Django File/InMemoryUploadedFile object
        
        Returns:
            dict: Analysis results or error message
        """
        try:
            # Check if ML API is healthy
            if not self.check_health():
                return {
                    'success': False,
                    'error': 'ML service is not available',
                    'status_code': 503
                }
            
            # Check if the model is ready
            if not self.check_model_status():
                return {
                    'success': False,
                    'error': 'ML model is still loading, please try again in a few moments',
                    'status_code': 503
                }
            
            # Prepare the file for upload
            files = {'file': (image_file.name, image_file, image_file.content_type)}
            
            # Send to ML API
            response = requests.post(
                f"{self.ml_api_url}/predict",
                files=files,
                timeout=30  # Longer timeout for prediction
            )
            
            # Process response
            if response.status_code == 200:
                result = response.json()
                
                # Format the response to match application needs
                return {
                    'success': True,
                    'diagnosis': result.get('diagnosis'),
                    'confidence': result.get('confidence'),
                    'details': result.get('class_probabilities', {}),
                    'image_size': result.get('image_size')
                }
            else:
                # Handle error response
                error_detail = 'Unknown error'
                try:
                    error_detail = response.json().get('detail', 'Unknown error')
                except:
                    error_detail = response.text or 'Unknown error'
                
                logger.error(f"ML API error: {response.status_code} - {error_detail}")
                return {
                    'success': False,
                    'error': error_detail,
                    'status_code': response.status_code
                }
                
        except requests.Timeout:
            logger.error("ML API request timed out")
            return {
                'success': False,
                'error': 'Request to ML service timed out',
                'status_code': 504
            }
        except Exception as e:
            logger.error(f"Error calling ML API: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'status_code': 500
            }

# Create a singleton instance
ml_service = ChestXrayService() 