import csv
from django.core.management.base import BaseCommand
from parivar.models import Person, ParentChildRelation, TranslatePerson
import os

class Command(BaseCommand):
    help = 'Export all main Person data to CSV files, separated by surname'

    def handle(self, *args, **options):
        # Create output directory
        export_dir = 'surname_exports'
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
            self.stdout.write(f"Created directory: {export_dir}")
        
        # Define headers to match the Excel screenshot exactly
        headers = [
            'Firstname (In English)', 'Firstname (In Gujarati)', 
            'Father name (In English)', 'Father name (In Gujarati)', 
            'Surname', 'Birth Date (DD-MM-YYYY)', 
            'Mobile Number Main', 'Mobile Number (Optional)', 'Country Name', 
            'International Mobile', 
            'Name of Father',
            # 'Name of Son'
        ]

        try:
            # 1. Discover all unique surnames
            unique_surnames = Person.objects.filter(
                is_deleted=False, 
                surname__isnull=False
            ).values_list('surname__name', flat=True).distinct().order_by('surname__name')
            
            self.stdout.write(f"Found {len(unique_surnames)} unique surnames. Starting batch export...")

            for surname_name in unique_surnames:
                if not surname_name:
                    continue
                    
                filename = os.path.join(export_dir, f"{surname_name}_Export.csv")
                
                # Filter persons by this specific surname
                persons = Person.objects.filter(surname__name=surname_name, is_deleted=False)
                
                # Use utf-8-sig for Excel compatibility with Gujarati characters
                with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=headers)
                    writer.writeheader()

                    for person in persons:
                        # Look up relations
                        father_relation = ParentChildRelation.objects.filter(child=person, is_deleted=False).first()
                        son_relation = ParentChildRelation.objects.filter(parent=person, is_deleted=False).first()
                        
                        # Look up Gujarati translations
                        translation = TranslatePerson.objects.filter(person_id=person, language='guj', is_deleted=False).first()
                        
                        # Professional Date Formatting (Strip time and normalize)
                        dob = person.date_of_birth or ''
                        if dob:
                            # Handle 'YYYY-MM-DD 00:00:00.000' and similar
                            clean_dob = dob.split(' ')[0]
                            if '-' in clean_dob:
                                parts = clean_dob.split('-')
                                if len(parts) == 3 and len(parts[0]) == 4:
                                    dob = f"{parts[2]}-{parts[1]}-{parts[0]}"
                                else:
                                    dob = clean_dob
                            else:
                                dob = clean_dob
                        
                        if '00:00:00' in dob or '0000-00-00' in dob:
                            dob = ''

                        row = {
                            'Firstname (In English)': person.first_name or '',
                            'Firstname (In Gujarati)': translation.first_name if translation else '',
                            'Father name (In English)': person.middle_name or '',
                            'Father name (In Gujarati)': translation.middle_name if translation else '',
                            'Surname': person.surname.name if person.surname else '',
                            'Birth Date (DD-MM-YYYY)': dob,
                            'Mobile Number Main': f'="{person.mobile_number1}"' if person.mobile_number1 else '',
                            'Mobile Number (Optional)': f'="{person.mobile_number2}"' if person.mobile_number2 else '',
                            'Country Name': (
                                person.out_of_country.name 
                                if person.out_of_country and person.out_of_country.name.lower() != 'india' 
                                else ''
                            ),
                            'International Mobile': f'="{person.out_of_mobile}"' if person.out_of_mobile else '',
                            'Name of Father': (
                                f"{father_relation.parent.first_name} {father_relation.parent.middle_name or ''}".strip()
                                if father_relation and father_relation.parent else ''
                            ),
                            # 'Name of Son': (
                            #     f"{son_relation.child.first_name} {son_relation.child.middle_name or ''}".strip()
                            #     if son_relation and son_relation.child else ''
                            # ),
                        }
                        writer.writerow(row)

                self.stdout.write(f"Successfully exported: {filename}")

            self.stdout.write(self.style.SUCCESS(f'\nFinished! All files are in the "{export_dir}" directory.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Export failed: {str(e)}'))
