from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q
import csv
import io
from .models import (
    DemoPerson, DemoBusiness, DemoBusinessCategory, 
    DemoNotification, DemoParentChildRelation,
    DemoBusinessSubCategory, DemoSurname,
    DemoState, DemoDistrict, DemoTaluka, DemoVillage,
    DemoCountry
)
from .serializers import (
    DemoPersonSerializer, DemoBusinessSerializer, 
    DemoBusinessCategorySerializer, DemoNotificationSerializer,
    DemoBusinessSubCategorySerializer, DemoStateSerializer,
    DemoDistrictSerializer, DemoTalukaSerializer, DemoVillageSerializer,
    DemoProfileSerializer, DemoPersonRegisterSerializer
)
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Common Parameters
lang_param = openapi.Parameter('lang', openapi.IN_QUERY, description="Language ('en' or 'guj')", type=openapi.TYPE_STRING)
state_id_param = openapi.Parameter('state_id', openapi.IN_QUERY, description="State ID", type=openapi.TYPE_INTEGER)
district_id_param = openapi.Parameter('district_id', openapi.IN_QUERY, description="District ID", type=openapi.TYPE_INTEGER)
taluka_id_param = openapi.Parameter('taluka_id', openapi.IN_QUERY, description="Taluka ID", type=openapi.TYPE_INTEGER)
category_id_param = openapi.Parameter('category', openapi.IN_QUERY, description="Category ID", type=openapi.TYPE_INTEGER)
subcategory_id_param = openapi.Parameter('subcategory', openapi.IN_QUERY, description="Sub-category ID", type=openapi.TYPE_INTEGER)
search_param = openapi.Parameter('search', openapi.IN_QUERY, description="Search term", type=openapi.TYPE_STRING)
person_id_param = openapi.Parameter('person_id', openapi.IN_QUERY, description="Person ID", type=openapi.TYPE_INTEGER, required=True)

class DemoLoginAPI(APIView):
    """Enhanced mock login mirroring main app logic"""
    @swagger_auto_schema(
        operation_description="Mock login for demo users",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['mobile_number1'],
            properties={
                'mobile_number1': openapi.Schema(type=openapi.TYPE_STRING, description="User mobile number"),
                'lang': openapi.Schema(type=openapi.TYPE_STRING, description="Language ('en' or 'guj')"),
            },
        ),
        tags=['Demo Auth']
    )
    def post(self, request):
        mobile = request.data.get("mobile_number1")
        lang = request.data.get("lang", "en")
        if not mobile:
            return Response({"message": "Mobile required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            person = DemoPerson.objects.get(Q(mobile_number1=mobile) | Q(mobile_number2=mobile))
            serializer = DemoPersonSerializer(person, context={"lang": lang})
            person_data = serializer.data
            
            # Mirroring main app response structure
            response_data = {
                "person": person_data,
                "admin_data": [], # Simplified for demo
                "pending-data": 0
            }
            
            if person.is_admin or person.is_super_admin:
                if person.is_super_admin:
                    pending_users = DemoPerson.objects.filter(flag_show=False)
                else:
                    pending_users = DemoPerson.objects.filter(
                        flag_show=False, 
                        village=person.village, 
                        surname=person.surname
                    )
                response_data["pending-data"] = pending_users.count()
            
            return Response(response_data, status=status.HTTP_200_OK)
        except DemoPerson.DoesNotExist:
            return Response({"message": "Person not found"}, status=status.HTTP_404_NOT_FOUND)

class DemoRegisterAPIView(APIView):
    """Member registration mirroring production flow"""
    @swagger_auto_schema(
        operation_description="Registration for demo members",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['first_name', 'surname', 'mobile_number1'],
            properties={
                'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                'middle_name': openapi.Schema(type=openapi.TYPE_STRING),
                'surname': openapi.Schema(type=openapi.TYPE_INTEGER),
                'father': openapi.Schema(type=openapi.TYPE_INTEGER, description="Parent person ID"),
                'child': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER)),
                'mobile_number1': openapi.Schema(type=openapi.TYPE_STRING),
                'mobile_number2': openapi.Schema(type=openapi.TYPE_STRING),
                'village': openapi.Schema(type=openapi.TYPE_INTEGER),
                'address': openapi.Schema(type=openapi.TYPE_STRING),
                'date_of_birth': openapi.Schema(type=openapi.TYPE_STRING),
                'lang': openapi.Schema(type=openapi.TYPE_STRING, default='en'),
            },
        ),
        tags=['Demo Auth']
    )
    def post(self, request):
        lang = request.data.get("lang", "en")
        father_id = request.data.get("father", 0)
        children_ids = request.data.get("child", [])
        
        serializer = DemoPersonRegisterSerializer(data=request.data)
        if serializer.is_valid():
            person = serializer.save(
                is_registered_directly=True,
                flag_show=False, # Production logic: Direct registers are pending
            )
            
            # Handle father relation
            if father_id:
                try:
                    father = DemoPerson.objects.get(id=father_id)
                    DemoParentChildRelation.objects.create(parent=father, child=person)
                except DemoPerson.DoesNotExist:
                    pass
            
            # Handle children relations
            for child_id in children_ids:
                try:
                    child = DemoPerson.objects.get(id=child_id)
                    DemoParentChildRelation.objects.create(parent=person, child=child)
                except DemoPerson.DoesNotExist:
                    pass
            
            person_data = DemoPersonSerializer(person, context={"lang": lang}).data
            
            # Mirroring production: return success message and admin contact
            msg = "તમારી નવા સભ્ય માં નોંધણી થઈ ગઈ છે. હવે તમે કૃપા કરી ને કાર્યકર્તાને સંપર્ક કરો." if lang == "guj" else "You are successfully registered. Please contact your admin for verification."
            
            return Response({
                "message": msg,
                "person": person_data,
                "admin_data": [] # In demo, we keep this simple
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DemoPersonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DemoPerson.objects.all()
    serializer_class = DemoPersonSerializer

    @swagger_auto_schema(manual_parameters=[lang_param], tags=['Demo Persons'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(manual_parameters=[lang_param], tags=['Demo Persons'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['lang'] = self.request.query_params.get('lang', 'en')
        return context

class DemoBusinessCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DemoBusinessCategory.objects.all()
    serializer_class = DemoBusinessCategorySerializer

    @swagger_auto_schema(manual_parameters=[lang_param], tags=['Demo Business'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(manual_parameters=[lang_param], tags=['Demo Business'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['lang'] = self.request.query_params.get('lang', 'en')
        return context

class DemoBusinessSubCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DemoBusinessSubCategory.objects.all()
    serializer_class = DemoBusinessSubCategorySerializer

    @swagger_auto_schema(manual_parameters=[lang_param, category_id_param], tags=['Demo Business'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(manual_parameters=[lang_param], tags=['Demo Business'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['lang'] = self.request.query_params.get('lang', 'en')
        return context

class DemoBusinessViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DemoBusiness.objects.all()
    serializer_class = DemoBusinessSerializer

    @swagger_auto_schema(
        manual_parameters=[lang_param, category_id_param, subcategory_id_param, search_param],
        tags=['Demo Business']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(manual_parameters=[lang_param], tags=['Demo Business'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        subcategory = self.request.query_params.get('subcategory')
        village = self.request.query_params.get('village')
        search = self.request.query_params.get('search')

        if category:
            queryset = queryset.filter(category_id=category)
        if subcategory:
            queryset = queryset.filter(subcategory_id=subcategory)
        if village:
            queryset = queryset.filter(village_id=village)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['lang'] = self.request.query_params.get('lang', 'en')
        return context

class DemoNotificationListView(APIView):
    @swagger_auto_schema(manual_parameters=[lang_param], tags=['Demo Notifications'])
    def get(self, request):
        lang = request.query_params.get('lang', 'en')
        notifications = DemoNotification.objects.all().order_by('-created_at')
        serializer = DemoNotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DemoStateListView(APIView):
    @swagger_auto_schema(manual_parameters=[lang_param], tags=['Demo Locations'])
    def get(self, request):
        lang = request.query_params.get('lang', 'en')
        states = DemoState.objects.all()
        serializer = DemoStateSerializer(states, many=True, context={'lang': lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class DemoDistrictListView(APIView):
    @swagger_auto_schema(manual_parameters=[lang_param, state_id_param], tags=['Demo Locations'])
    def get(self, request):
        state_id = request.query_params.get('state_id')
        lang = request.query_params.get('lang', 'en')
        queryset = DemoDistrict.objects.all()
        if state_id:
            queryset = queryset.filter(state_id=state_id)
        serializer = DemoDistrictSerializer(queryset, many=True, context={'lang': lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class DemoTalukaListView(APIView):
    @swagger_auto_schema(manual_parameters=[lang_param, district_id_param], tags=['Demo Locations'])
    def get(self, request):
        district_id = request.query_params.get('district_id')
        lang = request.query_params.get('lang', 'en')
        queryset = DemoTaluka.objects.all()
        if district_id:
            queryset = queryset.filter(district_id=district_id)
        serializer = DemoTalukaSerializer(queryset, many=True, context={'lang': lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class DemoVillageListView(APIView):
    @swagger_auto_schema(manual_parameters=[lang_param, taluka_id_param], tags=['Demo Locations'])
    def get(self, request):
        taluka_id = request.query_params.get('taluka_id')
        lang = request.query_params.get('lang', 'en')
        queryset = DemoVillage.objects.all()
        if taluka_id:
            queryset = queryset.filter(taluka_id=taluka_id)
        serializer = DemoVillageSerializer(queryset, many=True, context={'lang': lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class DemoRelationtreeAPIView(APIView):
    """Mirroring the RelationtreeAPIView logic for demo"""
    @swagger_auto_schema(manual_parameters=[lang_param, person_id_param], tags=['Demo Family Tree'])
    def get(self, request):
        lang = self.request.query_params.get('lang', 'en')
        person_id = self.request.query_params.get('person_id')

        if not person_id:
            return Response({"error": "person_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            person = DemoPerson.objects.get(id=person_id)
            surname = person.surname
            if not surname or not surname.top_member:
                # If no top member designated, just return siblings/parents
                person_data = DemoPerson.objects.filter(surname=surname).order_by("first_name")
                serializer = DemoPersonSerializer(person_data, many=True, context={"lang": lang})
                return Response({"data": serializer.data})

            topmember_id = surname.top_member.id
            
            # BFS to find all ancestors up to top_member
            relations = DemoParentChildRelation.objects.filter(child_id=person_id)
            parent_data_id = {int(person_id)}

            while relations:
                new_relations = []
                for relation in relations:
                    p_id = relation.parent.id
                    if p_id == topmember_id:
                        break
                    if p_id not in parent_data_id:
                        parent_data_id.add(p_id)
                        new_relations.extend(
                            DemoParentChildRelation.objects.filter(child_id=p_id)
                        )
                relations = new_relations
            
            # Return everyone in the surname EXCLUDING ancestors found above
            # This logic mirrors the original: it shows members who are NOT parents of the target person
            # but belong to the same surname.
            person_data = DemoPerson.objects.filter(surname=surname).exclude(id__in=parent_data_id).order_by("first_name")
            serializer = DemoPersonSerializer(person_data, many=True, context={"lang": lang})
            return Response({"data": serializer.data})

        except DemoPerson.DoesNotExist:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DemoProfileAPIView(APIView):
    """User profile with family and business details"""
    @swagger_auto_schema(manual_parameters=[lang_param, person_id_param], tags=['Demo Persons'])
    def get(self, request):
        lang = request.query_params.get('lang', 'en')
        person_id = request.query_params.get('person_id')

        if not person_id:
            return Response({"error": "person_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            person = DemoPerson.objects.get(id=person_id)
            serializer = DemoProfileSerializer(person, context={'lang': lang})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except DemoPerson.DoesNotExist:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)

class DemoCSVUploadAPIView(APIView):
    """Batch upload members and relations from CSV"""
    parser_classes = (MultiPartParser, FormParser)
    @swagger_auto_schema(
        operation_description="Upload members via CSV. Expected columns: first_name, middle_name, surname, mobile_number1, mobile_number2, village, is_out_of_country, country, country_mobile. Relations are automatically mapped using the Middle Name (Father's First Name) + Surname + Village.",
        manual_parameters=[
            openapi.Parameter('file', openapi.IN_FORM, type=openapi.TYPE_FILE, description="CSV File", required=True)
        ],
        responses={201: "Created successfully", 400: "Invalid data"},
        tags=['Demo Auth']
    )
    def post(self, request):
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        decoded_file = csv_file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        created_count = 0
        relations_staged = [] # (person_mobile, relation_mobile, type)

        def clean_val(val):
            if not val: return ''
            val = str(val).strip()
            if val.startswith('="') and val.endswith('"'):
                return val[2:-1]
            if val.startswith("'"): # Also handle single quote prefix
                return val[1:]
            return val
        
        for row in reader:
            try:
                # 1. Excel Header Mapping & Cleaning
                f_name = clean_val(row.get('Firstname (In English)') or row.get('first_name'))
                m_name = clean_val(row.get('Father name (In English)') or row.get('middle_name'))
                s_name = clean_val(row.get('Surname') or row.get('surname'))
                
                mob1 = clean_val(row.get('Mobile Number Main') or row.get('mobile_number1'))
                mob2 = clean_val(row.get('Mobile Number (Optional)') or row.get('mobile_number2'))
                
                country_name = clean_val(row.get('Country Name') or row.get('country'))
                int_mob = clean_val(row.get('International Mobile') or row.get('country_mobile'))

                # 2. Location Lookup (Simple name match for demo)
                village_name = clean_val(row.get('village', '')).strip()
                village = DemoVillage.objects.filter(name__icontains=village_name).first() if village_name else None
                
                surname, _ = DemoSurname.objects.get_or_create(name=s_name) if s_name else (None, False)
                
                # 3. International Support
                country, _ = DemoCountry.objects.get_or_create(name=country_name) if country_name else (None, False)
                is_out = (country is not None and country.name != 'India')
                
                # 4. Date Normalization (Support DD-MM-YYYY and YYYY-MM-DD)
                dob_raw = clean_val(row.get('Birth Date (DD-MM-YYYY)') or row.get('date_of_birth', ''))
                dob = dob_raw
                if dob_raw and '-' in dob_raw:
                    parts = dob_raw.split('-')
                    if len(parts) == 3:
                        # If YYYY-MM-DD, try to convert to DD-MM-YYYY for consistency
                        if len(parts[0]) == 4:
                            dob = f"{parts[2]}-{parts[1]}-{parts[0]}"
                
                # 5. Create/Update Person
                person_defaults = {
                        'first_name': f_name,
                        'middle_name': m_name,
                        'surname': surname,
                        'date_of_birth': dob,
                        'mobile_number2': mob2,
                        'village': village,
                        'is_out_of_country': is_out,
                        'out_of_country': country,
                        'country_mobile_number': int_mob,
                        'flag_show': True # Auto-approve CSV uploads in demo
                }
                if village:
                    person_defaults.update({
                        'state': village.taluka.district.state,
                        'district': village.taluka.district,
                        'taluka': village.taluka,
                    })

                if not mob1:
                    continue # Skip if main mobile is missing

                person, created = DemoPerson.objects.update_or_create(
                    mobile_number1=mob1,
                    defaults=person_defaults
                )
                
                # 4. Success Tracking
                if created:
                    created_count += 1
            except Exception as e:
                continue 

        # 5. Process Relations (Name-based identification)
        # We loop through all persons in the DB (including those just created) 
        # to establish links based on the First Name + Middle Name + Surname pattern.
        # This mirrors the cultural naming standard requested by the user.
        all_persons = DemoPerson.objects.all()
        for child in all_persons:
            father_name = child.middle_name
            if father_name and child.surname:
                # Find the father: match father's First Name with child's Middle Name
                # Matching surname and village makes the identification almost 100% sure.
                father = DemoPerson.objects.filter(
                    first_name__iexact=father_name,
                    surname=child.surname,
                    village=child.village
                ).exclude(id=child.id).first()
                
                if father:
                    DemoParentChildRelation.objects.get_or_create(parent=father, child=child)

        return Response({
            "message": f"Processed successfully. Created {created_count} new entries and updated family trees.",
            "total_processed": created_count
        }, status=status.HTTP_201_CREATED)
