from django.core.management.base import BaseCommand
from parivar.models import ParentChildRelation
from datetime import datetime, date

class Command(BaseCommand):
    help = 'Find and fix backwards parent-child relationships'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Actually fix the backwards relationships (default: just list them)',
        )

    def handle(self, *args, **options):
        fix_mode = options['fix']
        
        self.stdout.write('=' * 80)
        if fix_mode:
            self.stdout.write('FIXING BACKWARDS PARENT-CHILD RELATIONSHIPS')
        else:
            self.stdout.write('FINDING BACKWARDS PARENT-CHILD RELATIONSHIPS')
            self.stdout.write('(Run with --fix to actually swap them)')
        self.stdout.write('=' * 80)
        
        # Get relationships with dates
        relations = ParentChildRelation.objects.filter(
            is_deleted=False,
            parent__date_of_birth__isnull=False,
            child__date_of_birth__isnull=False
        ).select_related('parent', 'child')
        
        backwards_relations = []
        
        self.stdout.write(f'\nChecking {relations.count()} relationships...\n')
        
        for rel in relations:
            parent_dob = rel.parent.date_of_birth
            child_dob = rel.child.date_of_birth
            
            # Convert to date objects if needed
            if isinstance(parent_dob, str):
                for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']:
                    try:
                        parent_dob = datetime.strptime(parent_dob.split('.')[0], fmt).date()
                        break
                    except:
                        continue
            elif isinstance(parent_dob, datetime):
                parent_dob = parent_dob.date()
                
            if isinstance(child_dob, str):
                for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']:
                    try:
                        child_dob = datetime.strptime(child_dob.split('.')[0], fmt).date()
                        break
                    except:
                        continue
            elif isinstance(child_dob, datetime):
                child_dob = child_dob.date()
            
            # Check if backwards (child older than parent)
            if parent_dob > child_dob:
                backwards_relations.append({
                    'rel': rel,
                    'parent_dob': parent_dob,
                    'child_dob': child_dob
                })
        
        self.stdout.write('=' * 80)
        self.stdout.write(f'FOUND {len(backwards_relations)} BACKWARDS RELATIONSHIPS')
        self.stdout.write('=' * 80 + '\n')
        
        for item in backwards_relations:
            rel = item['rel']
            parent_dob = item['parent_dob']
            child_dob = item['child_dob']
            age_diff = (parent_dob - child_dob).days // 365
            
            self.stdout.write(f'\nRelationship ID: {rel.id} - ✗ BACKWARDS')
            self.stdout.write(f'  PARENT (should be CHILD): {rel.parent.first_name} {rel.parent.middle_name}')
            self.stdout.write(f'                            ID: {rel.parent.id}, DOB: {parent_dob}')
            self.stdout.write(f'  CHILD (should be PARENT):  {rel.child.first_name} {rel.child.middle_name}')
            self.stdout.write(f'                            ID: {rel.child.id}, DOB: {child_dob}')
            self.stdout.write(f'  Child is {age_diff} years OLDER than parent!')
        
        if fix_mode and backwards_relations:
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write('SWAPPING PARENT AND CHILD FIELDS')
            self.stdout.write('=' * 80 + '\n')
            
            fixed_count = 0
            for item in backwards_relations:
                rel = item['rel']
                
                # Swap parent and child
                temp_parent = rel.parent
                rel.parent = rel.child
                rel.child = temp_parent
                rel.save()
                
                fixed_count += 1
                self.stdout.write(f'Fixed relationship ID: {rel.id}')
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Fixed {fixed_count} backwards relationships!'))
        elif backwards_relations:
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.WARNING('To fix these relationships, run:'))
            self.stdout.write(self.style.WARNING('python manage.py fix_backwards_relationships --fix'))
            self.stdout.write('=' * 80)
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ No backwards relationships found!'))
