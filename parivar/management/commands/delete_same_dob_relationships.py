from django.core.management.base import BaseCommand
from parivar.models import ParentChildRelation
from datetime import datetime

class Command(BaseCommand):
    help = 'Find and delete relationships where parent and child have the same DOB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Actually delete the relationships (default: just list them)',
        )

    def handle(self, *args, **options):
        delete_mode = options['delete']
        
        self.stdout.write('=' * 80)
        if delete_mode:
            self.stdout.write('DELETING RELATIONSHIPS WITH SAME DOB')
        else:
            self.stdout.write('FINDING RELATIONSHIPS WITH SAME DOB')
            self.stdout.write('(Run with --delete to actually delete them)')
        self.stdout.write('=' * 80)
        
        # Get relationships with dates
        relations = ParentChildRelation.objects.filter(
            is_deleted=False,
            parent__date_of_birth__isnull=False,
            child__date_of_birth__isnull=False
        ).select_related('parent', 'child')
        
        same_dob_relations = []
        
        self.stdout.write(f'\nChecking {relations.count()} relationships...\n')
        
        for rel in relations:
            try:
                p_dob = rel.parent.date_of_birth
                c_dob = rel.child.date_of_birth
                
                # Convert to date objects if needed
                if isinstance(p_dob, str):
                    for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']:
                        try:
                            p_dob = datetime.strptime(p_dob.split('.')[0], fmt).date()
                            break
                        except:
                            continue
                elif isinstance(p_dob, datetime):
                    p_dob = p_dob.date()
                    
                if isinstance(c_dob, str):
                    for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']:
                        try:
                            c_dob = datetime.strptime(c_dob.split('.')[0], fmt).date()
                            break
                        except:
                            continue
                elif isinstance(c_dob, datetime):
                    c_dob = c_dob.date()
                
                # Check if same DOB (impossible for parent-child)
                if p_dob == c_dob:
                    same_dob_relations.append(rel)
            except:
                pass
        
        self.stdout.write('=' * 80)
        self.stdout.write(f'FOUND {len(same_dob_relations)} RELATIONSHIPS WITH SAME DOB')
        self.stdout.write('=' * 80 + '\n')
        
        for rel in same_dob_relations:
            p_dob = rel.parent.date_of_birth
            c_dob = rel.child.date_of_birth
            
            # Convert for display
            if isinstance(p_dob, str):
                for fmt in ['%Y-%m-%d', '%d-%m-%Y']:
                    try:
                        p_dob = datetime.strptime(p_dob.split('.')[0].split()[0], fmt).date()
                        break
                    except: pass
            if isinstance(c_dob, str):
                for fmt in ['%Y-%m-%d', '%d-%m-%Y']:
                    try:
                        c_dob = datetime.strptime(c_dob.split('.')[0].split()[0], fmt).date()
                        break
                    except: pass
            
            if hasattr(p_dob, 'date'): p_dob = p_dob.date()
            if hasattr(c_dob, 'date'): c_dob = c_dob.date()
            
            self.stdout.write(f'\nRelationship ID: {rel.id}')
            self.stdout.write(f'  PARENT: {rel.parent.first_name} {rel.parent.middle_name} (ID: {rel.parent.id})')
            self.stdout.write(f'          DOB: {p_dob}')
            self.stdout.write(f'  CHILD:  {rel.child.first_name} {rel.child.middle_name} (ID: {rel.child.id})')
            self.stdout.write(f'          DOB: {c_dob}')
            self.stdout.write(f'  ⚠️  SAME DATE OF BIRTH - Logically impossible!')
        
        if delete_mode and same_dob_relations:
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write('DELETING RELATIONSHIPS')
            self.stdout.write('=' * 80 + '\n')
            
            deleted_count = 0
            for rel in same_dob_relations:
                # Soft delete
                rel.is_deleted = True
                rel.save()
                
                deleted_count += 1
                self.stdout.write(f'Deleted relationship ID: {rel.id}')
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Deleted {deleted_count} relationships with same DOB!'))
            self.stdout.write('\nRun verify_relationships again to confirm.')
        elif same_dob_relations:
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.WARNING('To delete these relationships, run:'))
            self.stdout.write(self.style.WARNING('python manage.py delete_same_dob_relationships --delete'))
            self.stdout.write('=' * 80)
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ No relationships with same DOB found!'))
