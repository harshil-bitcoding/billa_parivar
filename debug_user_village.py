
import os
import django
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bila_parivar.settings')
django.setup()

from parivar.models import Person, Village

def debug_user(user_id):
    print(f"Checking user with ID: {user_id}")
    try:
        person = Person.objects.get(id=user_id)
        print(f"Name: {person.first_name} {person.middle_name} {person.surname.name if person.surname else ''}")
        
        if person.village:
            print(f"Village: {person.village.name} (ID: {person.village.id})")
            print(f"Village Referral Code: '{person.village.referral_code}'")
        else:
            print("Village: None (User is not assigned to any village)")
            
    except Person.DoesNotExist:
        print("User not found!")

if __name__ == "__main__":
    debug_user(2095)
