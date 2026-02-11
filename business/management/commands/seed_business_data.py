"""
Django management command to seed the database with sample business data
Usage: python manage.py seed_business_data
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from business.models import BusinessCategory, BusinessSubCategory, Business, BusinessOwner
from parivar.models import Person, Village, Taluka, District, State


class Command(BaseCommand):
    help = 'Seeds the database with sample business categories, subcategories, and businesses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing business data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing business data...'))
            Business.objects.all().delete()
            BusinessSubCategory.objects.all().delete()
            BusinessCategory.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Cleared existing data'))

        self.stdout.write(self.style.MIGRATE_HEADING('Starting business data seeding...'))
        
        with transaction.atomic():
            # Get the two persons to assign businesses to
            try:
                person_1772 = Person.objects.get(id=1772)
                person_1773 = Person.objects.get(id=1773)
                self.stdout.write(self.style.SUCCESS(f'✓ Found Person 1772: {person_1772.first_name}'))
                self.stdout.write(self.style.SUCCESS(f'✓ Found Person 1773: {person_1773.first_name}'))
            except Person.DoesNotExist as e:
                self.stdout.write(self.style.ERROR(f'Error: Person not found - {e}'))
                return
            
            # Get or create location data
            state, _ = State.objects.get_or_create(
                name='Gujarat',
                defaults={'guj_name': 'ગુજરાત'}
            )
            
            district, _ = District.objects.get_or_create(
                name='Ahmedabad',
                state=state,
                defaults={'guj_name': 'અમદાવાદ'}
            )
            
            taluka, _ = Taluka.objects.get_or_create(
                name='Ahmedabad City',
                district=district,
                defaults={'guj_name': 'અમદાવાદ શહેર'}
            )
            
            village, _ = Village.objects.get_or_create(
                name='Ahmedabad',
                taluka=taluka,
                defaults={'guj_name': 'અમદાવાદ'}
            )

            # Create categories and subcategories
            categories_data = [
                {
                    'name': 'Food & Beverages',
                    'guj_name': 'ખાદ્ય અને પીણાં',
                    'icon': 'restaurant',
                    'subcategories': [
                        {'name': 'Restaurant', 'guj_name': 'રેસ્ટોરન્ટ', 'icon': 'restaurant'},
                        {'name': 'Cafe', 'guj_name': 'કેફે', 'icon': 'local_cafe'},
                        {'name': 'Bakery', 'guj_name': 'બેકરી', 'icon': 'bakery_dining'},
                        {'name': 'Sweet Shop', 'guj_name': 'મીઠાઈની દુકાન', 'icon': 'cake'},
                    ]
                },
                {
                    'name': 'Retail & Shopping',
                    'guj_name': 'રિટેલ અને શોપિંગ',
                    'icon': 'shopping_bag',
                    'subcategories': [
                        {'name': 'Clothing Store', 'guj_name': 'કપડાની દુકાન', 'icon': 'checkroom'},
                        {'name': 'Grocery Store', 'guj_name': 'કરિયાણાની દુકાન', 'icon': 'local_grocery_store'},
                        {'name': 'Electronics', 'guj_name': 'ઇલેક્ટ્રોનિક્સ', 'icon': 'devices'},
                        {'name': 'Jewelry', 'guj_name': 'આભૂષણ', 'icon': 'diamond'},
                    ]
                },
                {
                    'name': 'Services',
                    'guj_name': 'સેવાઓ',
                    'icon': 'home_repair_service',
                    'subcategories': [
                        {'name': 'Salon & Spa', 'guj_name': 'સલૂન અને સ્પા', 'icon': 'content_cut'},
                        {'name': 'Repair Services', 'guj_name': 'રિપેર સેવાઓ', 'icon': 'build'},
                        {'name': 'Cleaning Services', 'guj_name': 'સફાઈ સેવાઓ', 'icon': 'cleaning_services'},
                        {'name': 'Photography', 'guj_name': 'ફોટોગ્રાફી', 'icon': 'photo_camera'},
                    ]
                },
                {
                    'name': 'Healthcare',
                    'guj_name': 'આરોગ્યસંભાળ',
                    'icon': 'local_hospital',
                    'subcategories': [
                        {'name': 'Clinic', 'guj_name': 'ક્લિનિક', 'icon': 'medical_services'},
                        {'name': 'Pharmacy', 'guj_name': 'દવાખાનું', 'icon': 'local_pharmacy'},
                        {'name': 'Diagnostic Center', 'guj_name': 'ડાયગ્નોસ્ટિક સેન્ટર', 'icon': 'biotech'},
                    ]
                },
                {
                    'name': 'Education',
                    'guj_name': 'શિક્ષણ',
                    'icon': 'school',
                    'subcategories': [
                        {'name': 'Coaching Classes', 'guj_name': 'કોચિંગ ક્લાસ', 'icon': 'menu_book'},
                        {'name': 'Computer Training', 'guj_name': 'કમ્પ્યુટર તાલીમ', 'icon': 'computer'},
                        {'name': 'Language Classes', 'guj_name': 'ભાષા વર્ગો', 'icon': 'translate'},
                    ]
                },
            ]

            created_categories = 0
            created_subcategories = 0
            created_businesses = 0
            
            # Alternate between person_1772 and person_1773
            person_1772_count = 0
            person_1773_count = 0

            for cat_data in categories_data:
                # Create category
                subcats = cat_data.pop('subcategories')
                category, created = BusinessCategory.objects.get_or_create(
                    name=cat_data['name'],
                    defaults={
                        'guj_name': cat_data['guj_name'],
                        'icon': cat_data['icon'],
                        'display_order': created_categories + 1
                    }
                )
                if created:
                    created_categories += 1
                    self.stdout.write(f'  ✓ Created category: {category.name}')

                # Create subcategories
                for idx, subcat_data in enumerate(subcats):
                    subcategory, created = BusinessSubCategory.objects.get_or_create(
                        category=category,
                        name=subcat_data['name'],
                        defaults={
                            'guj_name': subcat_data['guj_name'],
                            'icon': subcat_data['icon'],
                            'display_order': idx + 1
                        }
                    )
                    if created:
                        created_subcategories += 1
                        self.stdout.write(f'    ✓ Created subcategory: {subcategory.name}')

                    # Create 2-3 sample businesses for each subcategory
                    business_samples = self.get_business_samples(category.name, subcat_data['name'])
                    
                    for bus_data in business_samples:
                        # Alternate between the two persons
                        if created_businesses % 2 == 0:
                            owner_person = person_1772
                            person_1772_count += 1
                        else:
                            owner_person = person_1773
                            person_1773_count += 1
                        
                        business, created = Business.objects.get_or_create(
                            title=bus_data['title'],
                            defaults={
                                'description': bus_data['description'],
                                'category': category,
                                'subcategory': subcategory,
                                'village': village,
                                'taluka': taluka,
                                'district': district,
                                'state': state,
                                'contact_mobile': bus_data['mobile'],
                                'contact_whatsapp': bus_data['mobile'],
                                'keywords': bus_data['keywords'],
                                'is_verified': True,
                                'is_active': True,
                            }
                        )
                        
                        if created:
                            created_businesses += 1
                            
                            # Create owner linked to Person (registered owner)
                            BusinessOwner.objects.create(
                                business=business,
                                person=owner_person,  # Link to Person record
                                name=f"{owner_person.first_name} {owner_person.middle_name or ''}".strip(),
                                mobile=owner_person.mobile_number1 or bus_data['mobile'],
                                role='PRIMARY'
                            )
                            
                            self.stdout.write(f'      ✓ Created business: {business.title} (Owner: Person {owner_person.id})')

            self.stdout.write(self.style.SUCCESS(f'\n✓ Seeding completed successfully!'))
            self.stdout.write(self.style.SUCCESS(f'  Categories created: {created_categories}'))
            self.stdout.write(self.style.SUCCESS(f'  Subcategories created: {created_subcategories}'))
            self.stdout.write(self.style.SUCCESS(f'  Businesses created: {created_businesses}'))
            self.stdout.write(self.style.SUCCESS(f'  - Person 1772 owns: {person_1772_count} businesses'))
            self.stdout.write(self.style.SUCCESS(f'  - Person 1773 owns: {person_1773_count} businesses'))

    def get_business_samples(self, category, subcategory):
        """Returns sample business data based on category and subcategory"""
        
        samples = {
            ('Food & Beverages', 'Restaurant'): [
                {
                    'title': 'Honest Restaurant',
                    'description': 'Pure vegetarian Gujarati thali restaurant serving authentic homemade food',
                    'owner': 'Ramesh Patel',
                    'mobile': '9876543210',
                    'keywords': 'gujarati thali, vegetarian, homemade food'
                },
                {
                    'title': 'Spice Garden',
                    'description': 'Multi-cuisine restaurant with Chinese, Indian, and Continental dishes',
                    'owner': 'Suresh Shah',
                    'mobile': '9876543211',
                    'keywords': 'multi-cuisine, chinese, indian, continental'
                },
            ],
            ('Food & Beverages', 'Cafe'): [
                {
                    'title': 'Coffee Culture',
                    'description': 'Cozy cafe serving premium coffee, sandwiches, and desserts',
                    'owner': 'Priya Desai',
                    'mobile': '9876543212',
                    'keywords': 'coffee, cafe, sandwiches, desserts'
                },
            ],
            ('Food & Beverages', 'Bakery'): [
                {
                    'title': 'Fresh Bakes',
                    'description': 'Fresh bread, cakes, pastries, and cookies baked daily',
                    'owner': 'Kiran Mehta',
                    'mobile': '9876543213',
                    'keywords': 'bakery, bread, cakes, pastries'
                },
            ],
            ('Food & Beverages', 'Sweet Shop'): [
                {
                    'title': 'Shreeji Sweets',
                    'description': 'Traditional Gujarati sweets and farsan made with pure ghee',
                    'owner': 'Jayesh Joshi',
                    'mobile': '9876543214',
                    'keywords': 'sweets, farsan, gujarati, ghee'
                },
            ],
            ('Retail & Shopping', 'Clothing Store'): [
                {
                    'title': 'Fashion Hub',
                    'description': 'Latest fashion trends for men, women, and kids',
                    'owner': 'Neha Sharma',
                    'mobile': '9876543215',
                    'keywords': 'fashion, clothing, mens wear, womens wear'
                },
            ],
            ('Retail & Shopping', 'Grocery Store'): [
                {
                    'title': 'Daily Needs Supermarket',
                    'description': 'One-stop shop for all your daily grocery needs',
                    'owner': 'Ashok Kumar',
                    'mobile': '9876543216',
                    'keywords': 'grocery, supermarket, daily needs'
                },
            ],
            ('Services', 'Salon & Spa'): [
                {
                    'title': 'Glamour Salon',
                    'description': 'Professional hair styling, makeup, and spa services',
                    'owner': 'Ritu Agarwal',
                    'mobile': '9876543217',
                    'keywords': 'salon, spa, hair styling, makeup'
                },
            ],
            ('Healthcare', 'Clinic'): [
                {
                    'title': 'City Health Clinic',
                    'description': 'General physician consultation and basic health checkups',
                    'owner': 'Dr. Amit Patel',
                    'mobile': '9876543218',
                    'keywords': 'clinic, doctor, physician, health'
                },
            ],
            ('Healthcare', 'Pharmacy'): [
                {
                    'title': 'MedPlus Pharmacy',
                    'description': 'Genuine medicines and healthcare products at affordable prices',
                    'owner': 'Rajesh Modi',
                    'mobile': '9876543219',
                    'keywords': 'pharmacy, medicines, healthcare'
                },
            ],
            ('Education', 'Coaching Classes'): [
                {
                    'title': 'Bright Future Academy',
                    'description': 'Coaching for 10th, 12th, and competitive exams',
                    'owner': 'Prof. Vijay Trivedi',
                    'mobile': '9876543220',
                    'keywords': 'coaching, tuition, education, exams'
                },
            ],
        }
        
        # Return samples for this category/subcategory, or default sample
        key = (category, subcategory)
        if key in samples:
            return samples[key]
        else:
            # Default sample
            return [
                {
                    'title': f'Sample {subcategory}',
                    'description': f'A sample {subcategory.lower()} business in {category}',
                    'owner': 'Sample Owner',
                    'mobile': '9999999999',
                    'keywords': f'{subcategory.lower()}, {category.lower()}'
                }
            ]
