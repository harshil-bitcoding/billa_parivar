from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.db.models import Q, Count
from django.core import signing
from django.urls import reverse
from ..models import (
    Person, District, Taluka, Village, State, 
    TranslatePerson, Surname, ParentChildRelation, Country
)
import csv
import io
import openpyxl
from notifications.models import PersonPlayerId
from ..serializers import (
    DistrictSerializer,
    StateSerializer, 
    TalukaSerializer, 
    VillageSerializer, 
    PersonV4Serializer,
    SurnameSerializer
)
from ..views import getadmincontact
import logging
import os
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

logger = logging.getLogger(__name__)

class PendingApproveResponseSerializer(serializers.Serializer):
    child = PersonV4Serializer(many=True)
    others = PersonV4Serializer(many=True)

class DistrictDetailView(APIView):
    @swagger_auto_schema(
        operation_description="Get districts by state ID",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Districts list", schema=DistrictSerializer(many=True))}
    )
    def get(self, request, state_id):
        lang = request.GET.get("lang", "en")
        districts = District.objects.filter(state_id=state_id, is_active=True)
        serializer = DistrictSerializer(districts, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class TalukaDetailView(APIView):
    @swagger_auto_schema(
        operation_description="Get talukas by district ID",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Talukas list", schema=TalukaSerializer(many=True))}
    )
    def get(self, request, district_id):
        lang = request.GET.get("lang", "en")
        talukas = Taluka.objects.filter(
            district_id=district_id, 
            is_active=True, 
            district__is_active=True
        )
        serializer = TalukaSerializer(talukas, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class VillageDetailView(APIView):
    @swagger_auto_schema(
        operation_description="Get villages by taluka ID",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Villages list", schema=VillageSerializer(many=True))}
    )
    def get(self, request, taluka_id):
        lang = request.GET.get("lang", "en")
        villages = Village.objects.filter(
            taluka_id=taluka_id, 
            is_active=True, 
            taluka__is_active=True, 
            taluka__district__is_active=True
        )
        serializer = VillageSerializer(villages, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class SurnameByVillageView(APIView):
    """Returns only surnames that have members in a specific village."""
    @swagger_auto_schema(
        operation_description="Get surnames present in a specific village",
        manual_parameters=[
            openapi.Parameter('village_id', openapi.IN_QUERY, description="ID of the village", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Surnames list", schema=SurnameSerializer(many=True)), 400: "Village ID is required"}
    )
    def get(self, request):
        lang = request.GET.get("lang", "en")
        village_id = request.GET.get("village_id")
        
        if not village_id:
            return Response({"error": "Village ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            village = Village.objects.select_related('taluka', 'taluka__district').get(pk=village_id)
            if not village.is_active or not village.taluka.is_active or not village.taluka.district.is_active:
                msg = 'સંપર્ક કરો એડમિનિસ્ટ્રેટર (ગામ નિષ્ક્રિય છે)' if lang == 'guj' else 'Location deactivated. Please contact admin.'
                return Response({'message': msg}, status=status.HTTP_403_FORBIDDEN)
        except Village.DoesNotExist:
            return Response({'error': 'Village not found'}, status=status.HTTP_404_NOT_FOUND)
            
        # Get unique surname IDs for members in this village
        surname_ids = Person.objects.filter(
            village_id=village_id, is_deleted=False, flag_show=True
        ).values_list('surname_id', flat=True).distinct()
        
        surnames = Surname.objects.filter(id__in=surname_ids).order_by('name')
        serializer = SurnameSerializer(surnames, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class AdditionalDataByVillageView(APIView):
    """Returns statistics for a specific village."""
    @swagger_auto_schema(
        operation_description="Get statistics for a specific village",
        manual_parameters=[
            openapi.Parameter('village_id', openapi.IN_QUERY, description="ID of the village", type=openapi.TYPE_INTEGER, required=True)
        ],
        responses={200: openapi.Response(
            description="Village statistics",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'total_members': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'village_id': openapi.Schema(type=openapi.TYPE_INTEGER)
                }
            )
        ), 400: "Village ID is required"}
    )
    def get(self, request):
        village_id = request.GET.get("village_id")
        if not village_id:
            return Response({"error": "Village ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            village = Village.objects.select_related('taluka', 'taluka__district').get(pk=village_id)
            if not village.is_active or not village.taluka.is_active or not village.taluka.district.is_active:
                return Response({'message': 'Location deactivated. Please contact admin.'}, status=status.HTTP_403_FORBIDDEN)
        except Village.DoesNotExist:
            return Response({'error': 'Village not found'}, status=status.HTTP_404_NOT_FOUND)
            
        persons = Person.objects.filter(village_id=village_id, is_deleted=False, flag_show=True)
        total_members = persons.count()
        
        return Response({
            "total_members": total_members,
            "village_id": village_id
        }, status=status.HTTP_200_OK)

class PersonByVillageView(APIView):
    @swagger_auto_schema(
        operation_description="Filter persons based on village, optional surname and search keywords",
        manual_parameters=[
            openapi.Parameter('village_id', openapi.IN_QUERY, description="ID of the village", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('surname_id', openapi.IN_QUERY, description="Optional surname ID filter", type=openapi.TYPE_INTEGER),
            openapi.Parameter('search', openapi.IN_QUERY, description="Optional search keywords", type=openapi.TYPE_STRING),
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Persons list", schema=PersonV4Serializer(many=True)), 400: "Village ID is required"}
    )
    def get(self, request):
        lang = request.GET.get("lang", "en")
        village_id = request.GET.get("village_id")
        surname_id = request.GET.get("surname_id")
        
        if not village_id:
            return Response({"error": "Village ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        persons = Person.objects.filter(village_id=village_id, is_deleted=False, flag_show=True)
        
        if surname_id:
            persons = persons.filter(surname_id=surname_id)
            
        # Search functionality within village
        search = request.GET.get("search")
        if search:
            search_keywords = search.split(" ")
            query = Q()
            for keyword in search_keywords:
                query &= (
                    Q(first_name__icontains=keyword) |
                    Q(middle_name__icontains=keyword) |
                    Q(surname__name__icontains=keyword) |
                    Q(surname__guj_name__icontains=keyword) |
                    Q(translateperson__first_name__icontains=keyword)
                )
            persons = persons.filter(query).distinct()

        serializer = PersonV4Serializer(persons, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class V4LoginAPI(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="V4 Login API for members",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['mobile_number'],
            properties={
                'mobile_number': openapi.Schema(type=openapi.TYPE_STRING),
                'lang': openapi.Schema(type=openapi.TYPE_STRING, default='en'),
                'player_id': openapi.Schema(type=openapi.TYPE_STRING),
                'is_ios_platform': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False)
            }
        ),
        responses={200: "Success Login", 400: "Mobile number missing", 404: "Person not found"}
    )
    def post(self, request):
        mobile_number = request.data.get("mobile_number")
        lang = request.data.get("lang", "en")
        player_id = request.data.get("player_id", "")
        is_ios_platform = request.data.get("is_ios_platform", False)

        if not mobile_number:
            error_message = (
                "મોબાઈલ નંબર જરૂરી છે" if lang == "guj" else "Mobile number is required"
            )
            return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

        try:
            person = Person.objects.get(
                Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number),
                is_deleted=False,
            )
        except Person.DoesNotExist:
            error_message = "સભ્ય નોંધાયેલ નથી" if lang == "guj" else "Person not found"
            return Response({"message": error_message}, status=status.HTTP_404_NOT_FOUND)

        available_platform = "Ios" if is_ios_platform == True else "Android"

        if player_id:
            try:
                player_person = PersonPlayerId.objects.get(player_id=player_id)
                if player_person:
                    player_person.person = person
                    player_person.platform = available_platform
                    player_person.save()
            except Exception:
                PersonPlayerId.objects.create(
                    person=person,
                    player_id=player_id,
                    platform=available_platform,
                )

        serializer = PersonV4Serializer(
            person, context={"lang": lang, "person_id": person.id}
        )

        admin_data = getadmincontact(
            serializer.data.get("flag_show"), lang, serializer.data.get("surname")
        )
        
        admin_data["person"] = serializer.data
        
        admin_user_id = serializer.data.get("id")
        if admin_user_id:
            person_obj = Person.objects.get(pk=admin_user_id, is_deleted=False)
            if person_obj.is_admin or person_obj.is_super_admin:
                if person_obj.is_super_admin:
                    # Super admin sees all pending requests
                    pending_users = Person.objects.filter(
                        flag_show=False, is_deleted=False
                    )
                else:
                    # Village admin sees pending requests in their village with matching surname
                    pending_users = Person.objects.filter(
                        flag_show=False, 
                        village=person_obj.village, 
                        surname=person_obj.surname,
                        is_deleted=False
                    ).exclude(id=person_obj.surname.top_member if person_obj.surname else None)
                
                # Exclude top members if applicable (matching V3 logic style)
                # But here we probably want to exclude them from the count too if they are "system" members
                # For now, let's just count all pending in the village
                pendingdata_count = pending_users.count()
            else:
                pendingdata_count = 0
            
            response_data = {"pending-data": pendingdata_count}
            response_data.update(admin_data)
            return Response(response_data, status=status.HTTP_200_OK)
            
        return Response(admin_data, status=status.HTTP_200_OK)

class PendingApproveDetailViewV4(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Get list of pending approval requests for admins",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['admin_user_id'],
            properties={
                'admin_user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'lang': openapi.Schema(type=openapi.TYPE_STRING, default='en')
            }
        ),
        responses={
            200: openapi.Response(
                description="List of pending users",
                schema=PendingApproveResponseSerializer
            ),
            400: "Admin User ID missing",
            403: "No admin access",
            404: "User not found"
        }
    )
    def post(self, request):
        lang = request.data.get("lang", "en")
        admin_user_id = request.data.get("admin_user_id")
        
        if not admin_user_id:
            message = "એડમીન મળી રહીયો નથી" if lang == "guj" else "Missing Admin User"
            return Response({"message": message}, status=status.HTTP_400_BAD_REQUEST)

        try:
            admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
        except Person.DoesNotExist:
            return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if not admin_person.is_admin and not admin_person.is_super_admin:
            return Response({"message": "No admin access"}, status=status.HTTP_403_FORBIDDEN)

        if admin_person.is_super_admin:
            pending_users = Person.objects.filter(flag_show=False, is_deleted=False)
        else:
            # Filter by village and surname for village admin
            pending_users = Person.objects.filter(
                flag_show=False, 
                village=admin_person.village, 
                surname=admin_person.surname,
                is_deleted=False
            ).exclude(id=admin_person.surname.top_member if admin_person.surname else None)

        if not pending_users.exists():
            message = "કોઈ બાકી વિનંતી નથી" if lang == "guj" else "No pending requests"
            return Response({"message": message, "child": [], "others": []}, status=status.HTTP_200_OK)

        child_users = pending_users.filter(child_flag=True).order_by("first_name")
        other_users = pending_users.filter(child_flag=False).order_by("first_name")

        return Response({
            "child": PersonV4Serializer(child_users, many=True, context={"lang": lang}).data,
            "others": PersonV4Serializer(other_users, many=True, context={"lang": lang}).data,
        }, status=status.HTTP_200_OK)

class GenerateVillageInviteLinkView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Generate a secure invitation link for a village",
        responses={200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING),
                'invite_url': openapi.Schema(type=openapi.TYPE_STRING)
            }
        )}
    )
    def get(self, request, village_id):
        try:
            village = Village.objects.select_related('taluka', 'taluka__district').get(pk=village_id)
            if not village.is_active or not village.taluka.is_active or not village.taluka.district.is_active:
                return Response({"message": "Location deactivated. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)
        except Village.DoesNotExist:
            return Response({"error": "Village not found"}, status=status.HTTP_404_NOT_FOUND)

        data = {
            "v_id": village.id,
            "t_id": village.taluka.id,
            "d_id": village.taluka.district.id
        }
        
        token = signing.dumps(data)
        # Assuming the mobile app will handle this token via a deep link or the decode endpoint
        invite_url = request.build_absolute_uri(reverse('parivar:decode-invite-link', kwargs={'token': token}))
        
        return Response({
            "token": token,
            "invite_url": invite_url
        }, status=status.HTTP_200_OK)

class DecodeVillageInviteLinkView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Decode a village invitation token to get pre-fill data",
        responses={200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'village_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'taluka_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'district_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'village_name': openapi.Schema(type=openapi.TYPE_STRING),
                'taluka_name': openapi.Schema(type=openapi.TYPE_STRING),
                'district_name': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ), 400: "Invalid or expired token"}
    )
    def get(self, request, token):
        try:
            data = signing.loads(token)
            village = Village.objects.select_related('taluka', 'taluka__district').get(pk=data['v_id'])
            if not village.is_active or not village.taluka.is_active or not village.taluka.district.is_active:
                return Response({"message": "Location deactivated. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)
            
            return Response({
                "village_id": village.id,
                "taluka_id": village.taluka.id,
                "district_id": village.taluka.district.id,
                "village_name": village.name,
                "taluka_name": village.taluka.name,
                "district_name": village.taluka.district.name,
                "guj_village_name": village.guj_name,
                "guj_taluka_name": village.taluka.guj_name,
                "guj_district_name": village.taluka.district.guj_name,
            }, status=status.HTTP_200_OK)
        except (signing.BadSignature, Village.DoesNotExist):
            return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)

class AllVillageListView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Get list of all villages for initial registration selection",
        responses={200: openapi.Response(
            description="List of villages",
            schema=VillageSerializer(many=True)
        )}
    )
    def get(self, request):
        lang = request.GET.get("lang", "en")
        villages = Village.objects.filter(
            is_active=True, 
            taluka__is_active=True, 
            taluka__district__is_active=True
        ).order_by('name')
        serializer = VillageSerializer(villages, many=True, context={'lang': lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class VillageTalukaView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Get the parent Taluka for a village",
        responses={200: openapi.Response(
            description="Parent Taluka details",
            schema=TalukaSerializer
        ), 404: "Village not found"}
    )
    def get(self, request, village_id):
        try:
            village = Village.objects.select_related('taluka', 'taluka__district').get(pk=village_id)
            if not village.is_active or not village.taluka.is_active or not village.taluka.district.is_active:
                return Response({"message": "Location deactivated. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)
            serializer = TalukaSerializer(village.taluka, context={'lang': request.GET.get("lang", "en")})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Village.DoesNotExist:
            return Response({"error": "Village not found"}, status=status.HTTP_404_NOT_FOUND)

class TalukaDistrictView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Get the parent District for a taluka",
        responses={200: openapi.Response(
            description="Parent District details",
            schema=DistrictSerializer
        ), 404: "Taluka not found"}
    )
    def get(self, request, taluka_id):
        try:
            taluka = Taluka.objects.select_related('district').get(pk=taluka_id)
            if not taluka.is_active or not taluka.district.is_active:
                return Response({"message": "Location deactivated. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)
            serializer = DistrictSerializer(taluka.district, context={'lang': request.GET.get("lang", "en")})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Taluka.DoesNotExist:
            return Response({"error": "Taluka not found"}, status=status.HTTP_404_NOT_FOUND)

class DistrictStateView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Get the parent State for a district",
        responses={200: openapi.Response(
            description="Parent State details",
            schema=StateSerializer
        ), 404: "District not found"}
    )
    def get(self, request, district_id):
        try:
            district = District.objects.get(pk=district_id)
            if not district.is_active:
                return Response({"message": "Location deactivated. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)
            serializer = StateSerializer(district.state, context={'lang': request.GET.get("lang", "en")})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except District.DoesNotExist:
            return Response({"error": "District not found"}, status=status.HTTP_404_NOT_FOUND)

from rest_framework.parsers import MultiPartParser, FormParser

class CSVUploadAPIView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def clean_val(self, val):
        if not val:
            return ""
        val = str(val).strip()
        # Remove Excel formula wrapper ="value"
        if val.startswith('="') and val.endswith('"'):
            return val[2:-1]
        # Remove single quote prefix
        if val.startswith("'"):
            return val[1:]
        return val

    @swagger_auto_schema(
        operation_description="Upload members via CSV/XLSX. Supports Smart Header Detection for family books.",
        manual_parameters=[
            openapi.Parameter('file', openapi.IN_FORM, type=openapi.TYPE_FILE, description="CSV or XLSX File", required=True)
        ],
        responses={200: "Processed successfully", 400: "Invalid data"}
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
                sheet = wb.active
                for row in sheet.iter_rows(values_only=True):
                    rows.append(list(row))
            except Exception as e:
                return Response({"error": f"Failed to read XLSX: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Robust CSV Reading
            try:
                file_data = uploaded_file.read()
                try:
                    decoded = file_data.decode('utf-8-sig')
                except:
                    decoded = file_data.decode('latin-1')
                normalized = "\n".join(decoded.splitlines())
                reader = csv.reader(io.StringIO(normalized))
                for row in reader:
                    rows.append(row)
            except Exception as e:
                return Response({"error": f"Failed to read CSV: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        if not rows:
            return Response({"error": "File is empty"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Smart Header Detection
        header_row_idx = -1
        col_map = {}
        
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
            # Enhanced Row Detection
            row_str = " ".join(row)
            if any(k in row_str for k in ["Firstname", "Surname", "Sirname", "Father name", "Mobile"]):
                header_row_idx = i
                for j, cell in enumerate(row):
                    cell_val = str(cell).strip()
                    next_cell_val = str(rows[i+1][j]).strip() if i + 1 < len(rows) and j < len(rows[i+1]) and rows[i+1][j] else ""
                    
                    combined_col_str = f"{cell_val} {next_cell_val}"

                    if any(k in combined_col_str for k in keywords['first_name']):
                        if any(k in combined_col_str for k in keywords['gujarati']): col_map['first_name_guj'] = j
                        else: col_map['first_name'] = j
                    elif any(k in combined_col_str for k in keywords['middle_name']):
                        if any(k in combined_col_str for k in keywords['gujarati']): col_map['middle_name_guj'] = j
                        else: col_map['middle_name'] = j
                    elif any(k in combined_col_str for k in keywords['surname']): col_map['surname'] = j
                    elif any(k in combined_col_str for k in keywords['dob']): col_map['dob'] = j
                    elif any(k in combined_col_str for k in keywords['mobile1']):
                        if "Main" in combined_col_str: col_map['mobile1'] = j
                        elif "Optional" in combined_col_str: col_map['mobile2'] = j
                        elif 'mobile1' not in col_map: col_map['mobile1'] = j
                    elif any(k in combined_col_str for k in keywords['country']): col_map['country'] = j
                    elif any(k in combined_col_str for k in keywords['int_mobile']): col_map['int_mobile'] = j
                    elif any(k in combined_col_str for k in keywords['father_name']): col_map['father_name'] = j
                    elif any(k in combined_col_str for k in keywords['son_name']): col_map['son_name'] = j
                break

        if header_row_idx == -1:
            return Response({"error": "Could not identify header row. Ensure columns like 'Firstname', 'Surname', or 'Mobile' exist."}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Process Data
        created_count = 0
        updated_count = 0
        processed_rows = []

        def clean_val(val):
            if val is None: return ""
            val = str(val).strip()
            if val.startswith('="') and val.endswith('"'): return val[2:-1]
            if val.startswith("'"): return val[1:]
            return val

        start_row = header_row_idx + 1
        if start_row < len(rows):
            sub_row_str = " ".join([str(x) for x in rows[start_row]]).lower()
            if any(x in sub_row_str for x in ["english", "gujarati", "main", "optional", "link"]):
                start_row += 1

        for row in rows[start_row:]:
            if not any(row): continue
            
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
            surname_obj, _ = Surname.objects.get_or_create(name=s_name) if s_name else (None, False)
            
            # Default to India if blank
            c_name = country_name if country_name else "India"
            country_obj, _ = Country.objects.get_or_create(name=c_name)
            if not country_obj: country_obj = Country.objects.filter(id=1).first()

            # Date Normalization (DD-MM-YYYY -> YYYY-MM-DD)
            dob = ""
            if dob_raw:
                dob_str = str(dob_raw).split(' ')[0].replace('/', '-')
                if '-' in dob_str:
                    p = dob_str.split('-')
                    if len(p) == 3:
                        if len(p[0]) == 4: dob = f"{p[0]}-{p[1]}-{p[2]} 00:00:00.000"
                        else: dob = f"{p[2]}-{p[1]}-{p[0]} 00:00:00.000"

            person_defaults = {
                'first_name': f_name, 'middle_name': m_name, 'surname': surname_obj,
                'date_of_birth': dob, 'mobile_number2': mob2, 'out_of_country': country_obj,
                'out_of_mobile': int_mob, 'is_registered_directly': True, 'flag_show': True, 'platform': 'smart_import'
            }

            person, created = Person.objects.update_or_create(
                mobile_number1=mob1, is_deleted=False, defaults=person_defaults
            )

            # Handle Translation
            f_guj = clean_val(row[col_map['first_name_guj']]) if 'first_name_guj' in col_map and len(row) > col_map['first_name_guj'] else ""
            m_guj = clean_val(row[col_map['middle_name_guj']]) if 'middle_name_guj' in col_map and len(row) > col_map['middle_name_guj'] else ""
            if f_guj or m_guj:
                TranslatePerson.objects.update_or_create(
                    person_id=person, language='guj',
                    defaults={'first_name': f_guj or f_name, 'middle_name': m_guj or m_name, 'is_deleted': False}
                )

            if created: created_count += 1
            else: updated_count += 1
            processed_rows.append({
                'person': person,
                'father_name': clean_val(row[col_map['father_name']]) if 'father_name' in col_map and len(row) > col_map['father_name'] else "",
                'son_name': clean_val(row[col_map['son_name']]) if 'son_name' in col_map and len(row) > col_map['son_name'] else ""
            })

        # 4. Relations (High-Precision)
        for data in processed_rows:
            child = data['person']
            for name_field, is_parent in [(data['father_name'], True), (data['son_name'], False)]:
                if name_field:
                    p = name_field.split(' ')
                    q = Person.objects.filter(first_name__iexact=p[0], surname=child.surname, is_deleted=False)
                    if len(p) > 1: q = q.filter(middle_name__iexact=p[1])
                    if child.village: q = q.filter(village=child.village)
                    target = q.exclude(id=child.id).first()
                    if target:
                        ParentChildRelation.objects.get_or_create(
                            parent=(target if is_parent else child),
                            child=(child if is_parent else target),
                            defaults={'is_deleted': False}
                        )

        return Response({"message": f"Processed successfully. Created {created_count} and updated {updated_count} entries.", "created": created_count, "updated": updated_count}, status=status.HTTP_200_OK)
