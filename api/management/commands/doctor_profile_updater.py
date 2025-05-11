#!/usr/bin/env python
"""
Script to update profile pictures for doctor accounts

This script takes images from a directory and assigns them to doctor accounts
in the system. It ensures appropriate gender matching if possible.
"""

import os
import sys
import random
import django
from django.conf import settings
from django.core.files.base import ContentFile

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend_new.settings")
django.setup()

from api.models import User, Doctor

def update_doctor_profiles(images_dir="doctor_images"):
    """Update doctor profiles with images from the specified directory."""
    print(f"Starting doctor profile picture update from {images_dir}")
    
    # Check if the directory exists
    if not os.path.exists(images_dir):
        print(f"Creating {images_dir} directory")
        os.makedirs(images_dir)
        os.makedirs(os.path.join(images_dir, "male"), exist_ok=True)
        os.makedirs(os.path.join(images_dir, "female"), exist_ok=True)
        print(f"Please place doctor profile images in these directories and run the script again.")
        return
    
    male_dir = os.path.join(images_dir, "male")
    female_dir = os.path.join(images_dir, "female")
    
    # Check if gender directories exist
    if not os.path.exists(male_dir):
        os.makedirs(male_dir, exist_ok=True)
    if not os.path.exists(female_dir):
        os.makedirs(female_dir, exist_ok=True)
    
    # Get all images
    male_images = [os.path.join(male_dir, f) for f in os.listdir(male_dir) 
                  if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
    female_images = [os.path.join(female_dir, f) for f in os.listdir(female_dir) 
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
    
    # Check if enough images are available
    if not male_images:
        print("No male doctor images found. Please add some images in the male directory.")
    if not female_images:
        print("No female doctor images found. Please add some images in the female directory.")
    
    if not male_images and not female_images:
        return
    
    # Get all doctor accounts
    doctors = Doctor.objects.select_related('user').all()
    print(f"Found {doctors.count()} doctor accounts")
    
    # Track which images have been used
    used_male_images = []
    used_female_images = []
    
    updated_count = 0
    skipped_count = 0
    
    for doctor in doctors:
        user = doctor.user
        print(f"Processing doctor: {user.first_name} {user.last_name}")
        
        # Skip if user already has a profile picture
        if user.profile_picture:
            print(f"User {user.username} already has a profile picture, skipping")
            skipped_count += 1
            continue
        
        # Determine gender based on profile or best guess
        gender = doctor.gender
        
        if not gender:
            # Try to make an educated guess based on first name
            # This is a very basic approach and not culturally inclusive
            if user.first_name:
                if user.first_name.lower().endswith('a') or user.first_name.lower().endswith('e'):
                    gender = 'female'
                else:
                    gender = 'male'
            else:
                gender = random.choice(['male', 'female'])
        
        # Select appropriate image based on gender
        if gender == 'female' and female_images:
            available_images = [img for img in female_images if img not in used_female_images]
            if not available_images:
                # If all have been used, reset and use from the beginning
                used_female_images = []
                available_images = female_images
            
            image_path = random.choice(available_images)
            used_female_images.append(image_path)
        elif male_images:
            available_images = [img for img in male_images if img not in used_male_images]
            if not available_images:
                # If all have been used, reset and use from the beginning
                used_male_images = []
                available_images = male_images
            
            image_path = random.choice(available_images)
            used_male_images.append(image_path)
        else:
            # If we don't have the right gender image, use any available
            all_images = male_images + female_images
            image_path = random.choice(all_images)
        
        # Read and save the image to the user's profile picture
        try:
            with open(image_path, 'rb') as f:
                image_content = f.read()
                file_name = os.path.basename(image_path)
                user.profile_picture.save(file_name, ContentFile(image_content), save=True)
            
            # Also update doctor profile picture if it has one
            if hasattr(doctor, 'profile_picture'):
                doctor.profile_picture = user.profile_picture
                doctor.save()
                
            print(f"✅ Updated profile picture for {user.first_name} {user.last_name}")
            updated_count += 1
        except Exception as e:
            print(f"❌ Error updating profile for {user.username}: {str(e)}")
    
    print(f"\nProfile picture update complete! Summary:")
    print(f"  - Updated: {updated_count}")
    print(f"  - Skipped: {skipped_count}")
    print(f"  - Total doctors: {doctors.count()}")

if __name__ == "__main__":
    # Setup paths
    if len(sys.argv) > 1:
        update_doctor_profiles(sys.argv[1])
    else:
        update_doctor_profiles()