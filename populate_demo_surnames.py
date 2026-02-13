
import os
import django
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bila_parivar.settings')
django.setup()

from parivar.models import Surname, DemoPerson, DemoSurname

def populate_surnames():
    print("Starting Demo Surname Population...")
    
    # 1. Get all unique surname IDs used in DemoPerson
    # Note: These IDs currently refer to the MAIN Surname table logic (conceptually)
    used_surname_ids = DemoPerson.objects.values_list('surname_id', flat=True).distinct()
    
    print(f"Found {len(used_surname_ids)} unique surname IDs in DemoPerson records.")
    
    created_count = 0
    skipped_count = 0
    error_count = 0
    
    for s_id in used_surname_ids:
        if not s_id:
            continue
            
        # Check if already exists in DemoSurname
        if DemoSurname.objects.filter(id=s_id).exists():
            skipped_count += 1
            continue
            
        try:
            # Fetch from Main Surname Table
            main_surname = Surname.objects.get(id=s_id)
            
            # Find a valid top_member (DemoPerson)
            # Since we are migrating, we can just pick the first person with this surname
            top_member_person = DemoPerson.objects.filter(surname_id=main_surname.id).first()
            
            if not top_member_person:
                 print(f"Skipping {main_surname.name}: No DemoPerson found (Unexpected)")
                 continue

            # Create in DemoSurname
            DemoSurname.objects.create(
                id=main_surname.id, # Keep ID same to maintain FK integrity
                name=main_surname.name,
                guj_name=main_surname.guj_name,
                top_member=top_member_person
            )
            created_count += 1
            print(f"Created DemoSurname: {main_surname.name} (ID: {main_surname.id})")
            
        except Surname.DoesNotExist:
            print(f"Error: Surname ID {s_id} used in DemoPerson but not found in Main Surname table.")
            error_count += 1
        except Exception as e:
            print(f"Error processing ID {s_id}: {str(e)}")
            error_count += 1

    print("\n--- Summary ---")
    print(f"Total Unique IDs: {len(used_surname_ids)}")
    print(f"Created: {created_count}")
    print(f"Skipped (Already Exists): {skipped_count}")
    print(f"Errors: {error_count}")

if __name__ == "__main__":
    populate_surnames()
