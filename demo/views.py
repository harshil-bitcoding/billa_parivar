from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q
import csv
import io
import openpyxl
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
        
        # Make a mutable copy of the data to handle flexibility
        data = request.data.copy()
        
        # Handle flexible 'surname' (ID or Name string)
        surname_input = data.get('surname')
        if surname_input and isinstance(surname_input, str):
            surname_obj, _ = DemoSurname.objects.get_or_create(name=surname_input)
            data['surname'] = surname_obj.id
            
        # Handle flexible 'village' (ID or Name string)
        village_input = data.get('village')
        if village_input and isinstance(village_input, str):
            village_obj = DemoVillage.objects.filter(name__icontains=village_input).first()
            if village_obj:
                data['village'] = village_obj.id
            else:
                data.pop('village', None)

        # Handle flexible 'out_of_country' (ID or Name string)
        country_input = data.get('out_of_country')
        if country_input and isinstance(country_input, str):
            country_obj, _ = DemoCountry.objects.get_or_create(name=country_input)
            data['out_of_country'] = country_obj.id
        
        serializer = DemoPersonRegisterSerializer(data=data)
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
        operation_description="Upload members via CSV/XLSX. Supports Smart Header Detection for family books.",
        manual_parameters=[
            openapi.Parameter('file', openapi.IN_FORM, type=openapi.TYPE_FILE, description="CSV or XLSX File", required=True)
        ],
        responses={201: "Created successfully", 400: "Invalid data"},
        tags=['Demo Auth']
    )
    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        filename = uploaded_file.name.lower()
        rows = []

        # 1. Extract Rows (CSV or XLSX)
        if filename.endswith('.xlsx'):
            try:
                wb = openpyxl.load_workbook(uploaded_file, data_only=True)
                # Use first sheet or 'Thummar' sheet if it exists (for specific family book)
                sheet = wb.active
                for row in sheet.iter_rows(values_only=True):
                    rows.append(list(row))
            except Exception as e:
                return Response({"error": f"Failed to read XLSX: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Robust CSV Reading with Line Normalization
            try:
                file_data = uploaded_file.read()
                try:
                    decoded = file_data.decode('utf-8-sig')
                except:
                    decoded = file_data.decode('latin-1')
                # Normalize line endings
                normalized = "\n".join(decoded.splitlines())
                reader = csv.reader(io.StringIO(normalized))
                for row in reader:
                    rows.append(row)
            except Exception as e:
                return Response({"error": f"Failed to read CSV: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        if not rows:
            return Response({"error": "File is empty"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Smart Header Detection
        # Scan first 10 rows to find header row and map columns
        header_row_idx = -1
        col_map = {}
        
        # Keywords to look for in columns
        keywords = {
            'first_name': ['Firstname', 'First name', 'First Name'],
            'middle_name': ['Father name', 'Father Name'],
            'surname': ['Surname', 'Sirname'],
            'dob': ['Birth Date', 'Birt Date', 'DOB'],
            'mobile1': ['Mobile Number', 'Mobile Number Main', 'Main'],
            'mobile2': ['Optional', 'Secondary'],
            'country': ['Country Name', 'Outside India', 'Country'],
            'int_mobile': ['International Mobile', 'International'],
            'father_name': ['Name of Father'],
            'son_name': ['Name of Son'],
            'gujarati': ['Gujarati', 'In Gujara']
        }

        for i in range(min(10, len(rows))):
            row = [str(c).strip() if c else "" for c in rows[i]]
            # Enhanced Row Detection: Any major keyword is enough to suspect a header area
            row_str = " ".join(row)
            if any(k in row_str for k in ["Firstname", "Surname", "Sirname", "Father name", "Mobile"]):
                header_row_idx = i
                # Found it! Now map columns by checking current AND next row for EACH field
                for j, cell in enumerate(row):
                    cell_val = str(cell).strip()
                    
                    # Also look at the cell below (for split headers like 'Firstname' on row 1, 'In English' on row 2)
                    next_cell_val = ""
                    if i + 1 < len(rows) and j < len(rows[i+1]):
                        next_cell_val = str(rows[i+1][j]).strip() if rows[i+1][j] else ""
                    
                    combined_col_str = f"{cell_val} {next_cell_val}"

                    # Mapping logic using combined context
                    if any(k in combined_col_str for k in keywords['first_name']):
                        if any(k in combined_col_str for k in keywords['gujarati']): col_map['first_name_guj'] = j
                        else: col_map['first_name'] = j
                    elif any(k in combined_col_str for k in keywords['middle_name']):
                        if any(k in combined_col_str for k in keywords['gujarati']): col_map['middle_name_guj'] = j
                        else: col_map['middle_name'] = j
                    elif any(k in combined_col_str for k in keywords['surname']):
                        col_map['surname'] = j
                    elif any(k in combined_col_str for k in keywords['dob']):
                        col_map['dob'] = j
                    elif any(k in combined_col_str for k in keywords['mobile1']):
                        if "Main" in combined_col_str: col_map['mobile1'] = j
                        elif "Optional" in combined_col_str: col_map['mobile2'] = j
                        elif 'mobile1' not in col_map: col_map['mobile1'] = j
                    elif any(k in combined_col_str for k in keywords['country']):
                        col_map['country'] = j
                    elif any(k in combined_col_str for k in keywords['int_mobile']):
                        col_map['int_mobile'] = j
                    elif any(k in combined_col_str for k in keywords['father_name']):
                        col_map['father_name'] = j
                    elif any(k in combined_col_str for k in keywords['son_name']):
                        col_map['son_name'] = j
                break

        if header_row_idx == -1:
            return Response({"error": "Could not identify header row. Ensure columns like 'Firstname', 'Surname', or 'Mobile' exist."}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Process Data Rows
        created_count = 0
        updated_count = 0
        
        def clean_val(val):
            if val is None: return ""
            val = str(val).strip()
            if val.startswith('="') and val.endswith('"'): return val[2:-1]
            if val.startswith("'"): return val[1:]
            return val

        # Start from row AFTER header area
        start_row = header_row_idx + 1
        # Check if row+1 was actually a sub-header (scan it for non-data keywords)
        if start_row < len(rows):
            sub_row_str = " ".join([str(x) for x in rows[start_row]]).lower()
            if any(x in sub_row_str for x in ["english", "gujarati", "main", "optional", "link"]):
                start_row += 1

        for row in rows[start_row:]:
            if not any(row): continue # Skip empty rows
            
            # Extract data using map
            f_name = clean_val(row[col_map['first_name']]) if 'first_name' in col_map and len(row) > col_map['first_name'] else ""
            m_name = clean_val(row[col_map['middle_name']]) if 'middle_name' in col_map and len(row) > col_map['middle_name'] else ""
            s_name = clean_val(row[col_map['surname']]) if 'surname' in col_map and len(row) > col_map['surname'] else ""
            mob1 = clean_val(row[col_map['mobile1']]) if 'mobile1' in col_map and len(row) > col_map['mobile1'] else ""
            mob2 = clean_val(row[col_map['mobile2']]) if 'mobile2' in col_map and len(row) > col_map['mobile2'] else ""
            dob_raw = clean_val(row[col_map['dob']]) if 'dob' in col_map and len(row) > col_map['dob'] else ""
            country_name = clean_val(row[col_map['country']]) if 'country' in col_map and len(row) > col_map['country'] else ""
            int_mob = clean_val(row[col_map['int_mobile']]) if 'int_mobile' in col_map and len(row) > col_map['int_mobile'] else ""
            
            if not f_name or not mob1: continue

            # Create objects
            surname_obj, _ = DemoSurname.objects.get_or_create(name=s_name) if s_name else (None, False)
            
            # Default to India if blank
            c_name = country_name if country_name else "India"
            country_obj, _ = DemoCountry.objects.get_or_create(name=c_name)
            
            # DOB Normalization
            dob = dob_raw
            if dob_raw and '-' in str(dob_raw):
                parts = str(dob_raw).split('-')
                if len(parts) == 3 and len(parts[0]) == 4: # YYYY-MM-DD
                    dob = f"{parts[2]}-{parts[1]}-{parts[0]}"
            
            is_out = False
            if country_obj and country_obj.name.lower() != 'india':
                is_out = True

            person_defaults = {
                'first_name': f_name,
                'middle_name': m_name,
                'surname': surname_obj,
                'date_of_birth': dob,
                'mobile_number2': mob2,
                'is_out_of_country': is_out,
                'out_of_country': country_obj,
                'country_mobile_number': int_mob,
                'flag_show': True
            }

            person, created = DemoPerson.objects.update_or_create(
                mobile_number1=mob1,
                defaults=person_defaults
            )

            if created: created_count += 1
            else: updated_count += 1

        # 4. Process Relations (Name-based)
        all_persons = DemoPerson.objects.all()
        for child in all_persons:
            father_name = child.middle_name
            if father_name and child.surname:
                father = DemoPerson.objects.filter(
                    first_name__iexact=father_name,
                    surname=child.surname
                ).exclude(id=child.id).first()
                if father:
                    DemoParentChildRelation.objects.get_or_create(parent=father, child=child)

        return Response({
            "message": f"Processed successfully. Created {created_count} and updated {updated_count} entries.",
            "total_processed": created_count + updated_count
        }, status=status.HTTP_201_CREATED)
