import os
import uuid
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from rest_framework.exceptions import ValidationError

def generate_unique_filename(original_filename):
    ext = original_filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return filename

def save_uploaded_file(file, subdirectory):
    try:
        # Generate unique filename
        filename = generate_unique_filename(file.name)
        
        # Create the full path
        file_path = os.path.join(settings.MEDIA_ROOT, subdirectory, filename)
        
        # Save the file
        default_storage.save(file_path, ContentFile(file.read()))
        
        # Return the relative path
        return os.path.join(subdirectory, filename)
    except Exception as e:
        raise ValidationError(f"Error saving file: {str(e)}")

def delete_file(file_path):
    try:
        if file_path and default_storage.exists(file_path):
            default_storage.delete(file_path)
    except Exception as e:
        raise ValidationError(f"Error deleting file: {str(e)}")

def validate_image_file(file):
    # Check file size (max 5MB)
    max_size = 5 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError("File size should not exceed 5MB")
    
    # Check file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif']
    if file.content_type not in allowed_types:
        raise ValidationError("Only JPEG, PNG, and GIF images are allowed")

def validate_pdf_file(file):
    # Check file size (max 10MB)
    max_size = 10 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError("File size should not exceed 10MB")
    
    # Check file type
    if file.content_type != 'application/pdf':
        raise ValidationError("Only PDF files are allowed") 