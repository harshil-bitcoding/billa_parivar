import csv
from django.core.management.base import BaseCommand
from parivar.models import Person, ParentChildRelation, TranslatePerson
import os

class Command(BaseCommand):
    help = 'Export all main Person data to a CSV file'

    def handle(self, *args, **options):
        filename = 'persons_main_export.csv'
        
        # Define headers to match the Excel screenshot exactly
        headers = [
            'Firstname (In English)', 'Firstname (In Gujarati)', 
            'Father name (In English)', 'Father name (In Gujarati)', 
            'Surname', 'Birth Date (DD-MM-YYYY)', 
            'Mobile Number Main', 'Country Name', 
            'International Mobile', 'Mobile Number (Optional)', 
            'Name of Father', 'Name of Son'
        ]

        try:
            # Use utf-8-sig for Excel compatibility with Gujarati characters
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()

                persons = Person.objects.filter(surname__name__icontains="Thummar", is_deleted=False)
                self.stdout.write(f"Exporting {persons.count()} 'Thummar' persons from the main database...")

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
                        'Country Name': person.out_of_country.name if person.out_of_country else '',
                        'International Mobile': f'="{person.out_of_mobile}"' if person.out_of_mobile else '',
                        'Mobile Number (Optional)': f'="{person.mobile_number2}"' if person.mobile_number2 else '',
                        'Name of Father': (
                            f"{father_relation.parent.first_name} {father_relation.parent.middle_name or ''}".strip()
                            if father_relation and father_relation.parent else ''
                        ),
                        'Name of Son': (
                            f"{son_relation.child.first_name} {son_relation.child.middle_name or ''}".strip()
                            if son_relation and son_relation.child else ''
                        ),
                    }
                    writer.writerow(row)

            self.stdout.write(self.style.SUCCESS(f'Successfully exported main app data to {filename}'))
            self.stdout.write(f'File location: {os.path.abspath(filename)}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Export failed: {str(e)}'))
