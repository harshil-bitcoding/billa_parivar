from django.core.management.base import BaseCommand
from parivar.models import Person, Village, Samaj, Surname
from django.db.models import Count


class Command(BaseCommand):
    help = 'Populate district, taluka, village, and samaj for all persons'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting data population...'))
        
        # Get all persons without village assignment
        persons_without_location = Person.objects.filter(
            village__isnull=True,
            is_deleted=False
        ).select_related('surname')
        
        total_persons = persons_without_location.count()
        self.stdout.write(f'Found {total_persons} persons without location assignment')
        
        if total_persons == 0:
            self.stdout.write(self.style.WARNING('No persons to process'))
            return
        
        # Get all active villages
        villages = list(Village.objects.filter(
            is_active=True,
            taluka__is_active=True,
            taluka__district__is_active=True
        ).select_related('taluka', 'taluka__district'))
        
        if not villages:
            self.stdout.write(self.style.ERROR('No active villages found'))
            return
        
        self.stdout.write(f'Found {len(villages)} active villages')
        
        # Get existing samaj
        existing_samaj = list(Samaj.objects.all())
        self.stdout.write(f'Found {len(existing_samaj)} existing samaj')
        
        # Group persons by surname to keep families together
        surname_groups = {}
        for person in persons_without_location:
            surname_id = person.surname_id if person.surname_id else 'no_surname'
            if surname_id not in surname_groups:
                surname_groups[surname_id] = []
            surname_groups[surname_id].append(person)
        
        self.stdout.write(f'Grouped into {len(surname_groups)} surname groups')
        
        # Distribute surname groups across villages (round-robin)
        village_index = 0
        samaj_index = 0
        updated_count = 0
        
        for surname_id, persons_in_group in surname_groups.items():
            # Select village for this surname group
            village = villages[village_index % len(villages)]
            
            # Get or create samaj for this village
            # Cycle through the 3 existing samaj
            if existing_samaj:
                # Use existing samaj, but ensure it's linked to this village
                base_samaj = existing_samaj[samaj_index % len(existing_samaj)]
                
                # Try to find samaj with same name for this village
                samaj, created = Samaj.objects.get_or_create(
                    name=base_samaj.name,
                    village=village,
                    defaults={
                        'guj_name': base_samaj.guj_name,
                        'is_premium': base_samaj.is_premium,
                        'referral_code': f"{base_samaj.referral_code or base_samaj.name}_{village.id}" if base_samaj.referral_code else None
                    }
                )
                
                if created:
                    self.stdout.write(f'  Created samaj: {samaj.name} for village {village.name}')
                
                samaj_index += 1
            else:
                # Fallback: create default Patel samaj
                samaj, _ = Samaj.objects.get_or_create(
                    name='Patel',
                    village=village,
                    defaults={'guj_name': 'પટેલ', 'is_premium': False}
                )
            
            # Assign all persons in this surname group to the same village and samaj
            for person in persons_in_group:
                person.village = village
                person.taluka = village.taluka
                person.district = village.taluka.district
                person.samaj = samaj
                person.is_premium = samaj.is_premium
                person.save()
                updated_count += 1
            
            self.stdout.write(
                f'Assigned {len(persons_in_group)} persons (surname: {surname_id}) '
                f'to {village.name} ({samaj.name})'
            )
            
            village_index += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} persons'))
        
        # Show distribution summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write('DISTRIBUTION SUMMARY:')
        self.stdout.write('='*50)
        
        for village in villages:
            person_count = Person.objects.filter(village=village, is_deleted=False).count()
            samaj_in_village = Samaj.objects.filter(village=village)
            
            self.stdout.write(f'\n{village.name} ({village.taluka.name}, {village.taluka.district.name}):')
            self.stdout.write(f'  Total Persons: {person_count}')
            
            for samaj in samaj_in_village:
                samaj_person_count = Person.objects.filter(
                    village=village, 
                    samaj=samaj, 
                    is_deleted=False
                ).count()
                premium_status = '✓ Premium' if samaj.is_premium else '✗ Basic'
                self.stdout.write(f'    - {samaj.name}: {samaj_person_count} persons ({premium_status})')
