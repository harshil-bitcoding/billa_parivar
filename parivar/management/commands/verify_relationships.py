from django.core.management.base import BaseCommand
from parivar.models import ParentChildRelation, Person
from datetime import datetime, date

class Command(BaseCommand):
    help = 'Verify if parent-child relationships are correct in the database'

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('VERIFYING PARENT-CHILD RELATIONSHIPS')
        self.stdout.write('=' * 80)
        
        # Get all relationships
        total_relations = ParentChildRelation.objects.filter(is_deleted=False).count()
        self.stdout.write(f'\nTotal relationships: {total_relations}')
        
        # Get sample relationships with dates
        relations = ParentChildRelation.objects.filter(
            is_deleted=False,
            parent__date_of_birth__isnull=False,
            child__date_of_birth__isnull=False
        ).select_related('parent', 'child')
        
        correct_count = 0
        wrong_count = 0
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('SAMPLE RELATIONSHIPS (First 20 with DOB data)')
        self.stdout.write('=' * 80 + '\n')
        
        for rel in relations:
            parent_dob = rel.parent.date_of_birth
            child_dob = rel.child.date_of_birth
            
            # Convert to date objects if needed - handle multiple formats
            if isinstance(parent_dob, str):
                # Try different date formats
                for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']:
                    try:
                        parent_dob = datetime.strptime(parent_dob.split('.')[0], fmt).date()
                        break
                    except:
                        continue
            elif isinstance(parent_dob, datetime):
                parent_dob = parent_dob.date()
                
            if isinstance(child_dob, str):
                # Try different date formats
                for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']:
                    try:
                        child_dob = datetime.strptime(child_dob.split('.')[0], fmt).date()
                        break
                    except:
                        continue
            elif isinstance(child_dob, datetime):
                child_dob = child_dob.date()
            
            # Check if parent is older than child (should be True)
            is_correct = parent_dob < child_dob
            
            if is_correct:
                correct_count += 1
                status = '✓ CORRECT'
            else:
                wrong_count += 1
                status = '✗ WRONG!'
            
            self.stdout.write(f'\nRelationship ID: {rel.id} - {status}')
            self.stdout.write(f'  PARENT: {rel.parent.first_name} {rel.parent.middle_name}')
            self.stdout.write(f'          ID: {rel.parent.id}, DOB: {parent_dob}')
            self.stdout.write(f'  CHILD:  {rel.child.first_name} {rel.child.middle_name}')
            self.stdout.write(f'          ID: {rel.child.id}, DOB: {child_dob}')
            
            try:
                age_diff = (child_dob - parent_dob).days // 365
                self.stdout.write(f'  Age difference: {age_diff} years')
            except Exception as e:
                self.stdout.write(f'  Age difference: Unable to calculate - {e}')
        
        # Summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('SUMMARY')
        self.stdout.write('=' * 80)
        self.stdout.write(f'\nCorrect relationships (parent older than child): {correct_count}')
        self.stdout.write(f'Wrong relationships (child older than parent): {wrong_count}')
        
        if wrong_count > 0:
            percentage = (wrong_count / (correct_count + wrong_count)) * 100
            self.stdout.write(self.style.ERROR(f'\n⚠️  WARNING: {wrong_count} relationships ({percentage:.1f}%) are BACKWARDS!'))
            self.stdout.write(self.style.ERROR('The parent and child fields are swapped in the database.'))
            self.stdout.write('\nTo fix this, you would need to swap all parent-child fields.')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ All sampled relationships are CORRECT!'))
            self.stdout.write(self.style.SUCCESS('The parent field contains older persons (fathers).'))
            self.stdout.write(self.style.SUCCESS('The child field contains younger persons (sons).'))
            self.stdout.write('\n' + self.style.WARNING('If the mobile app shows them backwards, fix the mobile app display logic.'))
        
        self.stdout.write('\n' + '=' * 80)
