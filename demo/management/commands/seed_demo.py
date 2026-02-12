from django.core.management.base import BaseCommand
from demo.models import (
    DemoParentChildRelation, DemoBusinessCategory, 
    DemoBusinessSubCategory, DemoBusiness, DemoNotification,
    DemoState, DemoDistrict, DemoTaluka, DemoVillage, 
    DemoPerson, DemoSurname, DemoCountry
)
from django.db import transaction

class Command(BaseCommand):
    help = 'Production-grade seeder for demo app: Deep hierarchies and rich data volume'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Starting Production-Grade Demo Seeding...'))
        
        with transaction.atomic():
            print("Clearing existing demo data...")
            # 1. Clear existing demo data
            DemoNotification.objects.all().delete()
            DemoBusiness.objects.all().delete()
            DemoBusinessSubCategory.objects.all().delete()
            DemoBusinessCategory.objects.all().delete()
            DemoParentChildRelation.objects.all().delete()
            DemoPerson.objects.all().delete()
            DemoSurname.objects.all().delete()
            DemoVillage.objects.all().delete()
            DemoTaluka.objects.all().delete()
            DemoDistrict.objects.all().delete()
            DemoState.objects.all().delete()
            DemoCountry.objects.all().delete()

            # Seed Countries
            countries_data = [
                ('India', 'ભારત'), ('USA', 'યુએસએ'), ('Japan', 'જાપાન'), ('Canada', 'કેનેડા')
            ]
            for name, guj in countries_data:
                DemoCountry.objects.create(name=name, guj_name=guj)
            print("✓ Countries Seeded!")
            
            # 2. Seed 10 Locations (Chain: State -> District -> Taluka -> Village)
            states_info = [("Gujarat", "ગુજરાત"), ("Maharashtra", "મહારાષ્ટ્ર")]
            created_states = [DemoState.objects.create(name=n, guj_name=g) for n, g in states_info]
            
            districts_data = [
                ("Ahmedabad", "અમદાવાદ", 0), ("Surat", "સુરત", 0), ("Rajkot", "રાજકોટ", 0),
                ("Vadodara", "વડોદરા", 0), ("Bhavnagar", "ભાવનગર", 0), ("Mumbai", "મુંબઈ", 1),
                ("Pune", "પુણે", 1), ("Nagpur", "નાગપુર", 1), ("Nashik", "નાસિક", 1), ("Thane", "થાણે", 1)
            ]
            
            created_villages = []
            for d_name, d_guj, s_idx in districts_data:
                dist = DemoDistrict.objects.create(name=d_name, guj_name=d_guj, state=created_states[s_idx])
                taluka = DemoTaluka.objects.create(name=f"{d_name} Taluka", guj_name=f"{d_guj} તાલુકો", district=dist)
                village = DemoVillage.objects.create(name=f"{d_name} Village", guj_name=f"{d_guj} ગામ", taluka=taluka)
                created_villages.append(village)

            # 3. Seed Surnames
            surnames = [
                ("Patel", "પટેલ"), ("Shah", "શાહ"), ("Mehta", "મહેતા"), ("Desai", "દેસાઈ"), ("Joshi", "જોશી")
            ]
            created_surnames = [DemoSurname.objects.create(name=n, guj_name=g) for n, g in surnames]
            
            # 4. Seed 13 Persons (Extended for complex 4-level tree)
            people_data = [
                ("Mansukhbhai", "મનસુખભાઈ", 0, "9000000001", True),  # 0: G1
                ("Rajeshbhai", "રાજેશભાઈ", 0, "9000000002", False),  # 1: G2
                ("Sumanben", "સુમનબેન", 0, "9000000003", False),     # 2: G2
                ("Hardik", "હાર્દિક", 0, "9000000004", False),       # 3: G3
                ("Rahul", "રાહુલ", 0, "9000000005", False),           # 4: G3
                ("Nehal", "નેહલ", 0, "9000000006", False),           # 5: G3
                ("Chirag", "ચિરાગ", 0, "9000000007", False),           # 6: G4
                ("Sureshbhai", "સુરેશભાઈ", 1, "9000000008", False),  # 7
                ("Amitbhai", "અમિતભાઈ", 1, "9000000009", False),     # 8
                ("Vikrambhai", "વિક્રમભાઈ", 2, "9000000010", False),  # 9
                ("Deepakbhai", "દીપકભાઈ", 2, "9000000011", False),    # 10
                ("Sanjaybhai", "સંજયભાઈ", 3, "9000000012", False),    # 11
                ("Ashokbhai", "અશોકભાઈ", 4, "9000000013", True),     # 12
            ]
            
            created_people = []
            for i, (fn, guj_fn, s_idx, mobile, is_adm) in enumerate(people_data):
                v = created_villages[i % 10]
                p = DemoPerson.objects.create(
                    first_name=fn, guj_first_name=guj_fn,
                    surname=created_surnames[s_idx], mobile_number1=mobile,
                    state=v.taluka.district.state, 
                    district=v.taluka.district,
                    taluka=v.taluka,
                    village=v,
                    is_admin=is_adm
                )
                created_people.append(p)
                if not created_surnames[s_idx].top_member:
                    created_surnames[s_idx].top_member = p
                    created_surnames[s_idx].save()

            # 4.1 Seed 4-Level Family Tree
            # Patel Family
            DemoParentChildRelation.objects.create(parent=created_people[0], child=created_people[1]) # G1 -> G2
            DemoParentChildRelation.objects.create(parent=created_people[0], child=created_people[2]) # G1 -> G2 (Sibling)
            DemoParentChildRelation.objects.create(parent=created_people[1], child=created_people[3]) # G2 -> G3
            DemoParentChildRelation.objects.create(parent=created_people[1], child=created_people[4]) # G2 -> G3 (Sibling)
            DemoParentChildRelation.objects.create(parent=created_people[2], child=created_people[5]) # G2 -> G3 (Cousin)
            DemoParentChildRelation.objects.create(parent=created_people[3], child=created_people[6]) # G3 -> G4 (Great-grandchild)
            
            # Others
            DemoParentChildRelation.objects.create(parent=created_people[7], child=created_people[8])
            DemoParentChildRelation.objects.create(parent=created_people[9], child=created_people[10])

            # 5. Seed 10+ Business Categories & Sub-categories
            cats_info = [
                ("Food", "ખોરાક", "restaurant", ["Restaurant", "Cafe", "Bakery", "Ice Cream"]),
                ("Retail", "રિટેલ", "shopping_bag", ["Electronics", "Clothing", "Grocery", "Footwear"]),
                ("Services", "સેવાઓ", "build", ["Plumbing", "Electrical", "Legal", "Consultancy"])
            ]
            
            created_subcats = []
            for name, guj, icon, subs in cats_info:
                cat = DemoBusinessCategory.objects.create(name=name, guj_name=guj, icon=icon)
                for s_name in subs:
                    sub = DemoBusinessSubCategory.objects.create(category=cat, name=s_name, guj_name=f"{s_name} (Guj)")
                    created_subcats.append(sub)

            # 6. Seed 10 Businesses with Ownership Logic
            biz_data = [
                ("Sagar Restaurant", "સાગર રેસ્ટોરન્ટ", 0, [1, 3]), # Rajesh & Hardik
                ("Shah Electronics", "શાહ ઇલેક્ટ્રોનિક્સ", 4, [7, 8]), # Suresh & Amit
                ("Methta Clothing", "મહેતા ક્લોથિંગ", 5, [9]),
                ("Desai Legal", "દેસાઈ લીગલ", 10, [11]),
                ("City Cafe", "સિટી કેફે", 1, [1, 12]), # Rajesh & Ashok
                ("Apex Plumbing", "એપેક્સ પ્લમ્બિંગ", 8, [0, 12]), # Mansukh & Ashok
                ("Bakery Delight", "બેકરી ડિલાઇટ", 2, [9]),
                ("Tech World", "ટેક વર્લ્ડ", 4, [0]),
                ("Fashion Hub", "ફેશન હબ", 5, [12, 11]),
                ("Green Grocery", "ગ્રીન ગ્રોસરી", 6, [3, 7]),
            ]
            
            for i, (title, guj, sub_idx, owner_indices) in enumerate(biz_data):
                sub = created_subcats[sub_idx]
                v = created_villages[i % 10]
                biz = DemoBusiness.objects.create(
                    title=title, guj_title=guj,
                    description=f"Premium services at {title}",
                    category=sub.category, subcategory=sub,
                    village=v, contact_mobile=f"9876543{i:03}"
                )
                for o_idx in owner_indices:
                    biz.owners.add(created_people[o_idx])

            # 7. Seed 10 Notifications
            notif_data = [
                ("Welcome to Demo", "Explore our deep hierarchies", False, None, None),
                ("Grand Meeting", "Patel community meeting in Ahmedabad", True, None, created_surnames[0]),
                ("App Update", "Version 2.0 now live", False, None, None),
                ("Local Event", "Village gathering in Surat", True, created_villages[1], None),
                ("New Feature", "Family Tree visualization added", False, None, None),
                ("Business Summit", "Retailers meet in Mumbai", True, created_villages[5], None),
                ("Holiday Alert", "Office closed tomorrow", False, None, None),
                ("Special Discount", "Sagar Restaurant 20% off", False, None, None),
                ("Community News", "Mehta family achievement", False, None, created_surnames[2]),
                ("Service Alert", "System maintenance on Sunday", False, None, None),
            ]
            
            for title, sub, is_ev, v_target, s_target in notif_data:
                DemoNotification.objects.create(
                    title=title, subtitle=sub, is_event=is_ev,
                    village_target=v_target, surname_target=s_target
                )

        self.stdout.write(self.style.SUCCESS('✓ Production-Grade Seeding Completed Successfully!'))



# # 3. Date Normalization (Support DD-MM-YYYY and YYYY-MM-DD)
#                 dob_raw = row.get('Birth Date (DD-MM-YYYY)') or row.get('date_of_birth', '').strip()
#                 dob = dob_raw
#                 if dob_raw and '-' in dob_raw:
#                     parts = dob_raw.split('-')
#                     if len(parts) == 3:
#                         # If YYYY-MM-DD, try to convert to DD-MM-YYYY for consistency
#                         if len(parts[0]) == 4:
#                             dob = f"{parts[2]}-{parts[1]}-{parts[0]}"