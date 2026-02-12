import csv
from django.core.management.base import BaseCommand
from demo.models import DemoPerson, DemoParentChildRelation
import os

class Command(BaseCommand):
    help = 'Export all DemoPerson data to a CSV file'

    def handle(self, *args, **options):
        filename = 'demo_persons_export.csv'
        
        # Define headers exactly as shown in the screenshot + International Mobile
        headers = [
            'Firstname (In English)', 'Firstname (In Gujarati)', 
            'Father name (In English)', 'Father name (In Gujarati)', 
            'Surname', 'Birth Date (DD-MM-YYYY)', 
            'Mobile Number Main', 'Country Name', 
            'International Mobile', 'Mobile Number (Optional)', 
            'Name of Father', 'Name of Son'
        ]

        try:
            # Use utf-8-sig to ensure Excel recognizes Gujarati characters
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()

                persons = DemoPerson.objects.all()
                self.stdout.write(f"Exporting {persons.count()} persons...")

                for person in persons:
                    # Look up relations
                    father_relation = DemoParentChildRelation.objects.filter(child=person).first()
                    son_relation = DemoParentChildRelation.objects.filter(parent=person).first()
                    
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
                        'Firstname (In English)': person.first_name,
                        'Firstname (In Gujarati)': person.guj_first_name or '',
                        'Father name (In English)': person.middle_name or '',
                        'Father name (In Gujarati)': person.guj_middle_name or '',
                        'Surname': person.surname.name if person.surname else '',
                        'Birth Date (DD-MM-YYYY)': dob,
                        'Mobile Number Main': f'="{person.mobile_number1}"' if person.mobile_number1 else '',
                        'Country Name': person.out_of_country.name if person.out_of_country else '',
                        'International Mobile': f'="{person.country_mobile_number}"' if person.country_mobile_number else '',
                        'Mobile Number (Optional)': f'="{person.mobile_number2}"' if person.mobile_number2 else '',
                        'Name of Father': (
                            f"{father_relation.parent.first_name} {father_relation.parent.middle_name or ''} {father_relation.parent.surname.name if father_relation.parent.surname else ''}".strip()
                            if father_relation and father_relation.parent else ''
                        ),
                        'Name of Son': (
                            f"{son_relation.child.first_name} {son_relation.child.middle_name or ''} {son_relation.child.surname.name if son_relation.child.surname else ''}".strip()
                            if son_relation and son_relation.child else ''
                        ),
                    }
                    writer.writerow(row)

            self.stdout.write(self.style.SUCCESS(f'Successfully exported data to {filename}'))
            self.stdout.write(f'File location: {os.path.abspath(filename)}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Export failed: {str(e)}'))
