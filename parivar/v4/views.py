from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.db.models import Q, Count, Case, When, F, IntegerField, Value
from django.db.models.functions import Cast, Coalesce
from django.core import signing
from django.urls import reverse
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.db import transaction, IntegrityError
from datetime import datetime, timedelta
import numpy as np
import cv2
import string
import random
from ..models import (
    Person, District, Taluka, Village, State, 
    TranslatePerson, Surname, ParentChildRelation, Country,
    BloodGroup, Banner, AdsSetting, PersonUpdateLog, RandomBanner,
    DemoPerson, DemoParentChildRelation, DemoSurname
)
from ..services import LocationResolverService, CSVImportService
from django.conf import settings
from notifications.models import PersonPlayerId
from ..serializers import (
    DistrictSerializer,
    StateSerializer, 
    TalukaSerializer, 
    VillageSerializer, 
    PersonV4Serializer,
    SurnameSerializer,
    BloodGroupSerializer,
    ProfileSerializer,
    PersonSerializer,
    AdminPersonGetSerializer,
    GetParentChildRelationSerializer,
    PersonGetSerializer,
    GetSurnameSerializer,
    GetTreeRelationSerializer,
    GetSurnameSerializerdata,
    PersonDataAdminSerializer,
    BannerSerializer,
    BannerGETSerializer,
    PersonGetDataSortSerializer,
    ParentChildRelationSerializer,
    PersonSerializerV2,
    PersonGetSerializer2,
    TranslatePersonSerializer,
    CitySerializer,
    CountrySerializer,
    V4RelationTreeSerializer
)
from ..views import getadmincontact
import logging
import os
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from drf_yasg import openapi

logger = logging.getLogger(__name__)

class PendingApproveResponseSerializer(serializers.Serializer):
    child = PersonV4Serializer(many=True)
    others = PersonV4Serializer(many=True)

class DistrictDetailView(APIView):
    @swagger_auto_schema(
        operation_description="Get all districts",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Districts list", schema=DistrictSerializer(many=True))}
    )
    def get(self, request):
        lang = request.GET.get("lang", "en")
        districts = District.objects.filter(is_active=True)
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
        is_demo = request.GET.get("is_demo") == "true"
        person_model = DemoPerson if is_demo else Person
        
        surname_ids = person_model.objects.filter(
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
            
        is_demo = request.GET.get("is_demo") == "true"
        person_model = DemoPerson if is_demo else Person
        
        persons = person_model.objects.filter(village_id=village_id, is_deleted=False, flag_show=True)
        total_members = persons.count()
        
        return Response({
            "total_member": total_members,
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
        
        is_demo = request.GET.get("is_demo") == "true"
        person_model = DemoPerson if is_demo else Person
        
        persons = person_model.objects.filter(village_id=village_id, is_deleted=False, flag_show=True)
        
        if surname_id:
            persons = persons.filter(surname_id=surname_id)
            
        # Search functionality within village
        search = request.GET.get("search")
        if search:
            search_keywords = search.split(" ")
            query = Q()
            for keyword in search_keywords:
                keyword_query = (
                    Q(first_name__icontains=keyword) |
                    Q(middle_name__icontains=keyword) |
                    Q(surname__name__icontains=keyword) |
                    Q(surname__guj_name__icontains=keyword)
                )
                if is_demo:
                    keyword_query |= (
                        Q(guj_first_name__icontains=keyword) |
                        Q(guj_middle_name__icontains=keyword)
                    )
                else:
                    keyword_query |= Q(translateperson__first_name__icontains=keyword)
                
                query &= keyword_query
            persons = persons.filter(query).distinct()

        serializer = PersonV4Serializer(persons, many=True, context={"lang": lang, "is_demo": is_demo})
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)

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

        DEMO_MOBILE_NUMBER = "1111111111"
        is_demo = mobile_number == DEMO_MOBILE_NUMBER

        try:
            if is_demo:
                person = Person.objects.get(
                    Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number),
                    is_deleted=False,
                )
            else:
                is_demo_setting = mobile_number in getattr(settings, "DEMO_MOBILE_NUMBERS", [])
                if is_demo_setting:
                    person = DemoPerson.objects.get(
                        Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number),
                        is_deleted=False,
                    )
                    is_demo = True
                else:
                    person = Person.objects.get(
                        Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number),
                        is_deleted=False,
                    )
        except (Person.DoesNotExist, DemoPerson.DoesNotExist):
            error_message = "સભ્ય નોંધાયેલ નથી" if lang == "guj" else "Person not found"
            return Response({"message": error_message}, status=status.HTTP_404_NOT_FOUND)

        available_platform = "Ios" if is_ios_platform == True else "Android"

        if player_id and not is_demo:
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
            person, context={"lang": lang, "person_id": person.id, "is_demo": is_demo}
        )

        admin_data = getadmincontact(
            serializer.data.get("flag_show"), lang, serializer.data.get("surname_name")
        )
        
        admin_data["person"] = serializer.data
        
        # Add referral code for non-demo users
        admin_data["referral_code"] = ""
        if person.village and hasattr(person.village, 'referral_code') and person.village.referral_code:
            admin_data["referral_code"] = person.village.referral_code
        
        admin_user_id = serializer.data.get("id")
        if admin_user_id:
            if is_demo:
                pendingdata_count = 0
            else:
                try:
                    person_obj = Person.objects.get(pk=admin_user_id, is_deleted=False)
                    if person_obj.is_admin or person_obj.is_super_admin:
                        if person_obj.is_super_admin:
                            pending_users = Person.objects.filter(
                                flag_show=False, is_deleted=False
                            )
                        else:
                            pending_users = Person.objects.filter(
                                flag_show=False, 
                                village=person_obj.village, 
                                surname=person_obj.surname,
                                is_deleted=False
                            ).exclude(id=person_obj.surname.top_member if person_obj.surname else None)
                        pendingdata_count = pending_users.count()
                    else:
                        pendingdata_count = 0
                except Person.DoesNotExist:
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
            return Response({"message": message, "data": [], "child": [], "others": []}, status=status.HTTP_200_OK)

        child_users = pending_users.filter(child_flag=True).order_by("first_name")
        other_users = pending_users.filter(child_flag=False).order_by("first_name")

        child_serialized = PersonV4Serializer(child_users, many=True, context={"lang": lang}).data
        other_serialized = PersonV4Serializer(other_users, many=True, context={"lang": lang}).data

        return Response({
            "data": child_serialized + other_serialized,
            "child": child_serialized,
            "others": other_serialized,
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
        operation_description="Upload members via CSV/XLSX with strict location matching. Supports Dashboard sheet for referral codes.",
        manual_parameters=[
            openapi.Parameter('file', openapi.IN_FORM, type=openapi.TYPE_FILE, description="CSV or XLSX File", required=True)
        ],
        responses={200: "Processed successfully", 400: "Invalid data"}
    )
    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        result = CSVImportService.process_file(uploaded_file, request=request)
        
        if "error" in result:
            return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": f"Processed successfully. Created {result['created']} and updated {result['updated']} entries.",
            "created": result['created'],
            "updated": result['updated'],
            "bug_file": result['bug_file_url']
        }, status=status.HTTP_200_OK)


class V4AdminAccess(APIView):
    def get(self, request):
        lang = request.GET.get("lang", "en")
        admin_user_id = request.GET.get("admin_user_id")
        if not admin_user_id:
            if lang == "guj":
                return Response(
                    {"message": "એડમીન મળી રહીયો નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "Missing Admin User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        try:
            admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
        except Person.DoesNotExist:
            if lang == "en":
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": f"એડમિન વ્યક્તિ મળી રહી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        if not admin_person.is_super_admin:
            if lang == "en":
                return Response(
                    {
                        "message": "User does not have permission for create admin member"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "તમારી પાસે એડમિન સભ્ય બનાવવાની પરવાનગી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        admin_data = Person.objects.filter(
            Q(is_admin=True) | Q(is_super_admin=True), is_deleted=False
        )
        serializer = PersonGetSerializer(admin_data, context={"lang": lang}, many=True)
        return Response({"admin-data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        lang = request.data.get("lang", "en")
        mobile = request.data.get("mobile")
        admin_user_id = request.data.get("admin_user_id")
        if not admin_user_id:
            if lang == "guj":
                return Response(
                    {"message": "એડમીન મળી રહીયો નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "Missing Admin User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        try:
            admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
        except Person.DoesNotExist:
            if lang == "en":
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": f"એડમિન વ્યક્તિ મળી રહી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        if not admin_person.is_super_admin:
            if lang == "en":
                return Response(
                    {
                        "message": "User does not have permission for create admin member"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "તમારી પાસે એડમિન સભ્ય બનાવવાની પરવાનગી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        admin_access = Person.objects.filter(
            Q(mobile_number1__in=mobile) | Q(mobile_number2__in=mobile),
            is_deleted=False,
        )

        if admin_access:
            for admin in admin_access:
                if admin.flag_show == True:
                    mobile_last = admin.mobile_number1[-4:]
                    new_password = mobile_last
                    admin.is_admin = True
                    admin.password = new_password
                    admin.save()

            admin_access = admin_access.exclude(flag_show=True)
            serializer = PersonSerializer(admin_access, many=True)
            if admin_access.exists():
                error_message = ""
                for admin in serializer.data:
                    error_message += (
                        f"{admin.get('mobile_number1')} {admin.get('mobile_number2')} "
                    )
                if lang == "guj":
                    error_message += f"સભ્ય ની ચકાસણી અને અપડૅટ કરો"
                else:
                    error_message += f"Verify and update the member"
                return Response({"message": error_message})
            if lang == "guj":
                return Response(
                    {"message": "સફળતાપૂર્વક એડમિન બનાવ્યું"}, status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"message": "Succesfully admin Created"}, status=status.HTTP_200_OK
                )
        else:
            if lang == "guj":
                return Response(
                    {"message": "સભ્ય નોંધાયેલ નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "Member is Not registerd"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    def delete(self, request):
        lang = request.data.get("lang", "en")
        mobile = request.data.get("mobile")
        admin_user_id = request.data.get("admin_user_id")
        if not admin_user_id:
            if lang == "guj":
                return Response(
                    {"message": "એડમીન મળી રહીયો નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "Missing Admin User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        try:
            admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
        except Person.DoesNotExist:
            if lang == "en":
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": f"એડમિન વ્યક્તિ મળી રહી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        if not admin_person.is_super_admin:
            if lang == "en":
                return Response(
                    {
                        "message": "User does not have permission for to remove admin member"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "તમારી પાસે એડમિન સભ્ય કાઢવાની પરવાનગી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        admin_access = Person.objects.filter(
            Q(mobile_number1__in=mobile) | Q(mobile_number2__in=mobile),
            is_admin=True,
            is_deleted=False,
        )
        if admin_access:
            for admin in admin_access:
                if admin.flag_show == True:
                    admin.is_admin = False
                    admin.password = ""
                    admin.save()

        if lang == "guj":
            return Response(
                {"message": "સફળતાપૂર્વક એડમિન કાઢી નાખ્યું"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"message": "Succesfully admin remove"}, status=status.HTTP_200_OK
            )


class V4AdminPersons(APIView):
    def get(self, request):
        person_id = request.GET.get("person_id")
        if not person_id:
            return Response(
                {"message": "Please Enter a Person ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            person = Person.objects.get(id=person_id, is_deleted=False)
        except Person.DoesNotExist:
            return Response(
                {"message": "Person Not Found"}, status=status.HTTP_404_NOT_FOUND
            )

        lang = request.GET.get("lang", "en")
        admin_persons = Person.objects.filter(
            Q(is_admin=True) | Q(is_super_admin=True)
        ).order_by("first_name")
        surname_dict = {}
        for admin_person in admin_persons:
            surname_name = (
                admin_person.surname.name if admin_person.surname else "Unknown"
            )
            if surname_name not in surname_dict:
                surname_dict[surname_name] = []
            surname_dict[surname_name].append(admin_person)

        grouped_data = []
        for surname, persons in surname_dict.items():
            surname_serializer = GetSurnameSerializerdata(
                persons[0].surname, context={"lang": lang}
            )
            person_serializer = PersonDataAdminSerializer(
                persons, many=True, context={"lang": lang}
            )
            grouped_data.append(
                {"surname": surname_serializer.data, "persons": person_serializer.data}
            )

        return Response({"data": grouped_data}, status=status.HTTP_200_OK)

    def post(self, request):
        surname = request.data.get("surname")
        lang = request.data.get("lang", "en")
        if surname is None:

            if lang == "guj":
                return JsonResponse(
                    {"message": "અટક જરૂરી છે", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                return JsonResponse(
                    {"message": "Surname ID is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        surname_data = Surname.objects.filter(Q(id=int(surname)))
        if surname_data.exists():
            surname_data = surname_data.first()
            top_member = int(
                GetSurnameSerializer(surname_data).data.get("top_member", 0)
            )
            persons = (
                Person.objects.filter(
                    Q(surname__id=int(surname)),
                    is_admin=False,
                    is_super_admin=False,
                    flag_show=True,
                    mobile_number1__isnull=False,
                )
                .exclude(id=top_member)
                .exclude(mobile_number1__in=["", None])
                .order_by("first_name")
            )
            if persons.exists():
                serializer = PersonGetSerializer(
                    persons, many=True, context={"lang": lang}
                )
                if len(serializer.data) > 0:
                    data = sorted(
                        serializer.data,
                        key=lambda x: (x["first_name"], x["middle_name"], x["surname"]),
                    )
                    return JsonResponse({"data": data})
        return JsonResponse({"data": []}, status=status.HTTP_200_OK)

    def put(self, request):
        admin_user_id = request.data.get("admin_user_id")
        lang = request.data.get("lang", "en")
        password = request.data.get("password")

        # Ensure admin_user_id is provided
        if not admin_user_id:
            return Response(
                {"message": "admin_user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password:
            return Response(
                {"message": "new_password is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            person = Person.objects.get(id=admin_user_id, is_deleted=False)
            if person:
                person.password = password
                person.save()
            message = (
                "પાસવર્ડ સફળતાપૂર્વક બદલાઈ ગયું છે"
                if lang == "guj"
                else "Password Changed Successfully"
            )
            return Response({"message": message}, status=status.HTTP_200_OK)
        except Person.DoesNotExist:
            message = "સભ્ય મળ્યો નથી" if lang == "guj" else "Person not found"
            return Response({"message": message}, status=status.HTTP_404_NOT_FOUND)


def V4privacy_policy_app(request):
    return render(request, "privacy_policy.html")


def V4terms_condition_app(request):
    return render(request, "terms_condition.html")


class V4RelationtreeAPIView(APIView):
    def get(self, request):
        lang = request.GET.get("lang", "en")
        person_id = request.GET.get("person_id")
        is_demo = str(request.GET.get("is_demo")).lower() == "true"
        
        person_model = DemoPerson if is_demo else Person
        rel_model = DemoParentChildRelation if is_demo else ParentChildRelation
        surname_model = DemoSurname if is_demo else Surname

        try:
            if is_demo:
                 try:
                     person = person_model.objects.get(id=person_id, is_deleted=False)
                 except person_model.DoesNotExist:
                     # Fallback: If specific DemoPerson not found (e.g. Guest ID passed), use the first available DemoPerson
                     # Just get the first available person, ignoring strict surname validity check for now since DemoSurname might be empty
                     person = person_model.objects.filter(is_deleted=False).first()

                     if not person:
                         return Response({"error": "No Demo Data Available"}, status=status.HTTP_404_NOT_FOUND)
                     person_id = person.id
            else:
                person = person_model.objects.get(id=person_id, is_deleted=False)

            # Use surname_id to avoid direct FK lookup error if related object doesn't exist
            surname_id = person.surname_id
            surname_model = DemoSurname if is_demo else Surname
            
            try:
                surname_obj = surname_model.objects.get(id=surname_id)
            except surname_model.DoesNotExist:
                # Fallback: If DemoSurname doesn't exist (common in partial demo data), try valid Surname from main table
                if is_demo:
                    try:
                        surname_obj = Surname.objects.get(id=surname_id)
                    except Surname.DoesNotExist:
                         return Response({"error": "Surname not found"}, status=status.HTTP_404_NOT_FOUND)
                else:
                    return Response({"error": "Surname not found"}, status=status.HTTP_404_NOT_FOUND)

            topmember = surname_obj.top_member

            # Initialize relations with the first query
            relations = rel_model.objects.filter(child_id=person_id, is_deleted=False)
            parent_data_id = {
                int(person_id)
            }  # To keep track of already processed parent ids

            while relations:
                new_relations = []
                for relation in relations:
                    parent_id = relation.parent.id
                    if str(parent_id) == str(topmember):
                        break
                    if int(parent_id) not in parent_data_id:
                        parent_data_id.add(int(parent_id))
                        new_relations.extend(
                            rel_model.objects.filter(
                                child_id=parent_id, is_deleted=False
                            )
                        )
                relations = new_relations
            
            # Aligning with old response: total_count is the member count (excluding ancestors)
            person_query = person_model.objects.filter(
                surname__id=surname_id, flag_show=True, is_deleted=False
            ).exclude(id__in=parent_data_id)
            total_count = person_query.count()

            # Aligning with old response: data is a list of parent/child pairs
            relation_data = rel_model.objects.filter(
                child__surname_id=surname_id,
                parent__surname_id=surname_id,
                is_deleted=False
            ).exclude(child_id__in=parent_data_id).select_related('parent', 'child')

            serializer = V4RelationTreeSerializer(
                relation_data, many=True, context={"lang": lang, "is_demo": is_demo}
            )

            return Response({
                "total_count": total_count,
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except (Person.DoesNotExist, DemoPerson.DoesNotExist):
            return Response(
                {"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            #     {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            # )


def V4index(request):
    return HttpResponse("Hello, world. This is the index page.")


class V4BloodGroupDetailView(APIView):
    authentication_classes = []

    def get(self, request):
        bloodgroup = BloodGroup.objects.all()
        serializer = BloodGroupSerializer(bloodgroup, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class V4ProfileDetailView(APIView):
    authentication_classes = []

    def post(self, request, id):
        try:
            try:
                id = int(id)
            except ValueError:
                return Response(
                    {"error": "Invalid ID format"}, status=status.HTTP_400_BAD_REQUEST
                )
            person = get_object_or_404(Person, pk=id)
            serializer = ProfileSerializer(person, data=request.data)
            serializer.is_valid(raise_exception=True)
            profile = serializer.save()
            if "profile_image" in request.FILES:
                profile.profile_image = request.FILES["profile_image"]
                profile.save()
            return Response(
                {"success": "Profile data updated successfully!"},
                status=status.HTTP_200_OK,
            )
        except Person.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error saving profile: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class V4PersonDetailView(APIView):
    authentication_classes = []

    def get(self, request, pk):
        is_demo = request.GET.get("is_demo") == "true"
        model = DemoPerson if is_demo else Person
        rel_model = DemoParentChildRelation if is_demo else ParentChildRelation
        
        try:
            person_obj = model.objects.get(id=pk)
            if person_obj:
                lang = request.GET.get("lang", "en")
                person_data = PersonGetSerializer(person_obj, context={"lang": lang, "is_demo": is_demo}).data
                person_data["child"] = []
                person_data["parent"] = {}
                person_data["brother"] = []
                child_data = rel_model.objects.filter(parent=int(person_data["id"]), is_deleted=False)
                if child_data.exists():
                    child_data = GetParentChildRelationSerializer(
                        child_data, many=True, context={"lang": lang, "is_demo": is_demo}
                    ).data
                    for child in child_data:
                        person_data["child"].append(child.get("child"))
                parent_relation = rel_model.objects.filter(
                    child=int(person_data["id"]), is_deleted=False
                ).first()
                if parent_relation:
                    parent_relation_data = GetParentChildRelationSerializer(
                        parent_relation, context={"lang": lang, "is_demo": is_demo}
                    ).data
                    person_data["parent"] = parent_relation_data.get("parent")
                    brother_data = rel_model.objects.filter(
                        parent=int(parent_relation_data.get("parent").get("id", 0)),
                        is_deleted=False
                    )
                    if brother_data.exists():
                        brother_data_serializer = GetParentChildRelationSerializer(
                            brother_data, many=True, context={"lang": lang, "is_demo": is_demo}
                        ).data
                        for brother in brother_data_serializer:
                            if int(person_data["id"]) != int(brother["child"]["id"]):
                                person_data["brother"].append(brother.get("child"))
                return Response(person_data, status=status.HTTP_200_OK)
        except Person.DoesNotExist:
            return Response(
                {"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        surname = request.data.get("surname", 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get("father", 0)
        top_member = 0
        if persons_surname_wise:
            top_member = int(
                GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0)
            )
            if father == 0:
                father = top_member
        children = request.data.get("child", [])
        first_name = request.data.get("first_name")
        middle_name = request.data.get("middle_name")
        address = request.data.get("address")
        out_of_address = request.data.get("out_of_address")
        lang = request.data.get("lang", "en")
        date_of_birth = request.data.get("date_of_birth")
        blood_group = request.data.get("blood_group", 1)
        city = request.data.get("city")
        state = request.data.get("state")
        out_of_country = request.data.get("out_of_country", 1)
        if int(out_of_country) == 0:
            out_of_country = 1
        flag_show = request.data.get("flag_show")
        mobile_number1 = request.data.get("mobile_number1")
        mobile_number2 = request.data.get("mobile_number2")
        status_name = request.data.get("status")
        is_admin = request.data.get("is_admin")
        is_registered_directly = request.data.get("is_registered_directly")
        person_data = {
            "first_name": first_name,
            "middle_name": middle_name,
            "address": address,
            "out_of_address": out_of_address,
            "date_of_birth": date_of_birth,
            "blood_group": blood_group,
            "city": city,
            "state": state,
            "out_of_country": out_of_country,
            "flag_show": flag_show,
            "mobile_number1": mobile_number1,
            "mobile_number2": mobile_number2,
            "status": status_name,
            "surname": surname,
            "is_admin": is_admin,
            "is_registered_directly": is_registered_directly,
        }
        serializer = PersonSerializer(data=person_data)
        if serializer.is_valid():
            if len(children) > 0:
                children_exist = ParentChildRelation.objects.filter(child__in=children)
                if children_exist.exclude(parent=top_member).exists():
                    return JsonResponse({"message": "Children already exist"}, status=400)
                children_exist.filter(parent=top_member).delete()
            persons = serializer.save()
            try:
                if not first_name:
                    raise ValueError("first_name is required")
                from django.contrib.auth.models import User
                user, user_created = User.objects.get_or_create(username=first_name)
                if user_created:
                    user.set_password(
                        "".join(random.choices(string.ascii_letters + string.digits, k=12))
                    )
                user.save()
            except IntegrityError as e:
                print(f"IntegrityError encountered: {e}")
            parent_serializer = ParentChildRelationSerializer(
                data={"parent": father, "child": persons.id, "created_user": persons.id}
            )
            if parent_serializer.is_valid():
                parent_serializer.save()
            for child in children:
                child_serializer = ParentChildRelationSerializer(
                    data={
                        "child": child,
                        "parent": persons.id,
                        "created_user": persons.id,
                    }
                )
                if child_serializer.is_valid():
                    child_serializer.save()
            if lang != "en":
                person_translate_data = {
                    "first_name": first_name,
                    "person_id": persons.id,
                    "middle_name": middle_name,
                    "address": address,
                    "out_of_address": out_of_address,
                    "language": lang,
                }
                person_translate_serializer = TranslatePersonSerializer(
                    data=person_translate_data
                )
                if person_translate_serializer.is_valid():
                    person_translate_serializer.save()
            return Response(
                PersonGetSerializer(persons, context={"lang": lang}).data,
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        person = get_object_or_404(Person, pk=pk)
        if not person:
            return JsonResponse(
                {"message": "Person not found"}, status=status.HTTP_400_BAD_REQUEST
            )
        surname = request.data.get("surname", 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get("father", 0)
        top_member = 0
        if persons_surname_wise:
            top_member = int(
                GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0)
            )
            if father == 0:
                father = top_member
        children = request.data.get("child", [])
        first_name = request.data.get("first_name")
        middle_name = request.data.get("middle_name")
        address = request.data.get("address")
        out_of_address = request.data.get("out_of_address")
        lang = request.data.get("lang", "en")
        date_of_birth = request.data.get("date_of_birth")
        blood_group = request.data.get("blood_group", 1)
        city = request.data.get("city")
        state = request.data.get("state")
        out_of_country = request.data.get("out_of_country", 1)
        if int(out_of_country) == 0:
            out_of_country = 1
        flag_show = request.data.get("flag_show")
        mobile_number1 = request.data.get("mobile_number1")
        mobile_number2 = request.data.get("mobile_number2")
        status_name = request.data.get("status")
        is_admin = request.data.get("is_admin")
        is_registered_directly = request.data.get("is_registered_directly")
        person_data = {
            "first_name": person.first_name if lang == "en" else first_name,
            "middle_name": person.middle_name if lang == "en" else middle_name,
            "address": person.address if lang == "en" else address,
            "out_of_address": out_of_address,
            "date_of_birth": date_of_birth,
            "blood_group": blood_group,
            "city": city,
            "state": state,
            "out_of_country": out_of_country,
            "flag_show": flag_show,
            "mobile_number1": mobile_number1,
            "mobile_number2": mobile_number2,
            "status": status_name,
            "surname": surname,
            "is_admin": is_admin,
            "is_registered_directly": is_registered_directly,
        }

        ignore_fields = [
            "update_field_message",
            "id",
            "flag_show",
            "is_admin",
            "is_registered_directly",
        ]
        update_field_message = []
        for field, new_value in person_data.items():
            if field in ignore_fields:
                continue
            old_value = getattr(person, field, None)

            if hasattr(old_value, "id"):
                old_value = old_value.id

            if old_value != new_value:
                update_field_message.append(
                    {"field": field, "previous": old_value, "new": new_value}
                )

        if update_field_message:
            person.update_field_message = str(update_field_message)

        serializer = PersonSerializer(
            person, data=person_data, context={"person_id": person.id}
        )
        if serializer.is_valid():
            if len(children) > 0:
                children_exist = ParentChildRelation.objects.filter(child__in=children)
                if (
                    children_exist.exclude(parent=top_member)
                    .exclude(parent=person.id)
                    .exists()
                ):
                    return JsonResponse({"message": "Children already exist"}, status=400)
            persons = serializer.save()

            father_data = ParentChildRelation.objects.filter(child=persons.id)
            data = {"parent": father, "child": persons.id, "created_user": persons.id}
            father_data_serializer = None
            if father_data.exists():
                father_data = father_data.first()
                father_data_serializer = ParentChildRelationSerializer(
                    father_data, data=data
                )
            else:
                father_data_serializer = ParentChildRelationSerializer(data=data)
            if father_data_serializer.is_valid():
                father_data_serializer.save()
            for child in children:
                child_data = ParentChildRelation.objects.filter(child=child)
                data = {
                    "child": child,
                    "parent": persons.id,
                    "created_user": persons.id,
                }
                child_data_serializer = None
                if child_data.exists():
                    child_data = child_data.first()
                    child_data_serializer = ParentChildRelationSerializer(
                        child_data, data=data
                    )
                else:
                    child_data_serializer = ParentChildRelationSerializer(data=data)
                if child_data_serializer.is_valid():
                    child_data_serializer.save()
            if len(children) > 0:
                remove_child_person = ParentChildRelation.objects.filter(
                    parent=persons.id
                ).exclude(child__in=children)
                if remove_child_person.exists():
                    for child in remove_child_person:
                        child.parent_id = int(top_member)
                        child.save()
            if lang != "en":
                lang_data = TranslatePerson.objects.filter(person_id=persons.id).filter(
                    language=lang
                )
                if lang_data.exists():
                    lang_data = lang_data.first()
                    person_translate_data = {
                        "first_name": first_name,
                        "middle_name": middle_name,
                        "address": address,
                        "out_of_address": out_of_address,
                        "language": lang,
                    }
                    person_translate_serializer = TranslatePersonSerializer(
                        lang_data, data=person_translate_data
                    )
                    if person_translate_serializer.is_valid():
                        person_translate_serializer.save()
            return Response(
                {"person": PersonGetSerializer(persons, context={"lang": lang}).data},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        person = get_object_or_404(Person, pk=pk)
        try:
            person.delete()
            return Response(
                {"message": "Person record deleted successfully."},
                status=status.HTTP_204_NO_CONTENT,
            )
        except Exception as e:
            return Response(
                {"message": f"Failed to delete the person record: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class V4AdminPersonDetailView(APIView):
    authentication_classes = []

    def get(self, request, pk, admin_uid):
        admin_user_id = admin_uid
        if not admin_user_id:
            return Response(
                {"message": "Missing Admin User in request data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            admin_person = Person.objects.get(pk=admin_user_id)
        except Person.DoesNotExist:
            return Response(
                {"message": f"Admin Person not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if not admin_person.is_admin and not admin_person.is_super_admin:
            return Response(
                {"message": "User does not have admin access"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            person = Person.objects.get(id=pk)
            if person:
                lang = request.GET.get("lang", "en")
                person = AdminPersonGetSerializer(person, context={"lang": lang}).data
                person["child"] = []
                person["parent"] = {}
                person["brother"] = []
                child_data = ParentChildRelation.objects.filter(parent=int(person["id"]))
                if child_data.exists():
                    child_data = GetParentChildRelationSerializer(
                        child_data, many=True, context={"lang": lang}
                    ).data
                    for child in child_data:
                        person["child"].append(child.get("child"))
                parent_data = ParentChildRelation.objects.filter(
                    child=int(person["id"])
                ).first()
                if parent_data:
                    parent_data = GetParentChildRelationSerializer(
                        parent_data, context={"lang": lang}
                    ).data
                    person["parent"] = parent_data.get("parent")
                    brother_data = ParentChildRelation.objects.filter(
                        parent=int(parent_data.get("parent").get("id", 0))
                    )
                    if brother_data.exists():
                        brother_data = GetParentChildRelationSerializer(
                            brother_data, many=True, context={"lang": lang}
                        ).data
                        for brother in brother_data:
                            if int(person["id"]) != int(brother["child"]["id"]):
                                person["brother"].append(brother.get("child"))
                return Response(person, status=status.HTTP_200_OK)
        except Person.DoesNotExist:
            return Response(
                {"error": "Person not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        admin_user_id = request.data.get("admin_user_id")
        if admin_user_id is None:
            return Response(
                {"message": "Missing Admin User ID in request data"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            admin_person = Person.objects.get(pk=admin_user_id)
        except Person.DoesNotExist:
            return Response(
                {"message": "Admin Person with that ID does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not admin_person.is_admin:
            return Response(
                {"message": "User does not have admin access"},
                status=status.HTTP_200_OK,
            )
        surname = request.data.get("surname", 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get("father", 0)
        top_member = 0
        if persons_surname_wise:
            top_member = int(
                GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0)
            )
            if father == 0:
                father = top_member
        children = request.data.get("child", [])
        if len(children) > 0:
            children_exist = ParentChildRelation.objects.filter(child__in=children)
            if children_exist.exclude(parent=top_member).exists():
                return JsonResponse({"message": "Children already exist"}, status=400)
            children_exist.filter(parent=top_member).delete()
        first_name = request.data.get("first_name")
        middle_name = request.data.get("middle_name")
        address = request.data.get("address")
        out_of_country = request.data.get("out_of_country", 1)
        if int(out_of_country) == 0:
            out_of_country = 1
        out_of_address = request.data.get("out_of_address")
        guj_first_name = request.data.get("guj_first_name")
        guj_middle_name = request.data.get("guj_middle_name")
        guj_address = request.data.get("guj_address")
        guj_out_of_address = request.data.get("guj_out_of_address")
        lang = request.data.get("lang")
        if lang is not None and lang != "en":
            if guj_first_name is None or guj_first_name == "":
                return JsonResponse({"message": "First Name is required"}, status=400)
            if (
                first_name is None
                or first_name == ""
                and guj_first_name is not None
                and guj_first_name != ""
            ):
                first_name = guj_first_name
            if (
                middle_name is None or middle_name == ""
            ) and guj_middle_name is not None and guj_middle_name != "":
                middle_name = guj_middle_name
            if (
                address is None or address == ""
            ) and guj_address is not None and guj_address != "":
                address = guj_address
            if (
                out_of_address is None or out_of_address == ""
            ) and guj_out_of_address is not None and guj_out_of_address != "":
                out_of_address = guj_out_of_address
        date_of_birth = request.data.get("date_of_birth")
        blood_group = request.data.get("blood_group")
        city = request.data.get("city")
        state = request.data.get("state")
        mobile_number1 = request.data.get("mobile_number1")
        mobile_number2 = request.data.get("mobile_number2")
        status_name = request.data.get("status")
        is_admin = request.data.get("is_admin")
        is_registered_directly = request.data.get("is_registered_directly")
        person_data = {
            "first_name": first_name,
            "middle_name": middle_name,
            "address": address,
            "out_of_address": out_of_address,
            "date_of_birth": date_of_birth,
            "blood_group": blood_group,
            "out_of_country": out_of_country,
            "city": city,
            "state": state,
            "flag_show": True,
            "mobile_number1": mobile_number1,
            "mobile_number2": mobile_number2,
            "status": status_name,
            "surname": surname,
            "is_admin": is_admin,
            "is_registered_directly": is_registered_directly,
        }
        serializer = PersonSerializer(data=person_data)
        if serializer.is_valid():
            persons = serializer.save()
            parent_serializer = ParentChildRelationSerializer(
                data={"parent": father, "child": persons.id, "created_user": persons.id}
            )
            if parent_serializer.is_valid():
                parent_serializer.save()

            for child in children:
                child_serializer = ParentChildRelationSerializer(
                    data={
                        "child": child,
                        "parent": persons.id,
                        "created_user": persons.id,
                    }
                )

                if child_serializer.is_valid():
                    child_serializer.save()
            person_translate_data = {
                "first_name": guj_first_name,
                "person_id": persons.id,
                "middle_name": guj_middle_name,
                "out_of_address": guj_out_of_address,
                "address": guj_address,
                "language": lang,
            }
            person_translate_serializer = TranslatePersonSerializer(
                data=person_translate_data
            )
            if person_translate_serializer.is_valid():
                person_translate_serializer.save()
            return Response(
                {"person": AdminPersonGetSerializer(persons).data},
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        admin_user_id = request.data.get("admin_user_id")
        if not admin_user_id:
            return Response(
                {"message": "Missing Admin User in request data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            admin_person = Person.objects.get(pk=admin_user_id)
        except Person.DoesNotExist:
            return Response(
                {"message": f"Admin Person not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if not admin_person.is_admin and not admin_person.is_super_admin:
            return Response(
                {"message": "User does not have admin access"},
                status=status.HTTP_200_OK,
            )

        user_id = request.data.get("user_id")
        if not user_id:
            return Response(
                {"message": "Missing User in request data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        person = get_object_or_404(Person, pk=user_id)
        if not person:
            return JsonResponse(
                {"message": "Person not found"}, status=status.HTTP_400_BAD_REQUEST
            )
        surname = request.data.get("surname", 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get("father", 0)
        top_member = 0
        if persons_surname_wise:
            top_member = int(
                GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0)
            )
            if father == 0:
                father = top_member
        children = request.data.get("child", [])
        first_name = request.data.get("first_name")
        middle_name = request.data.get("middle_name")
        address = request.data.get("address")
        out_of_address = request.data.get("out_of_address")
        lang = request.data.get("lang", "en")
        date_of_birth = request.data.get("date_of_birth")
        blood_group = request.data.get("blood_group", 1)
        out_of_country = request.data.get("out_of_country", 1)
        if int(out_of_country) == 0:
            out_of_country = 1
        guj_first_name = request.data.get("guj_first_name")
        guj_middle_name = request.data.get("guj_middle_name")
        guj_address = request.data.get("guj_address")
        guj_out_of_address = request.data.get("guj_out_of_address")
        flag_show = request.data.get("flag_show")
        if flag_show is None:
            flag_show = True
        mobile_number1 = request.data.get("mobile_number1")
        mobile_number2 = request.data.get("mobile_number2")

        status_name = request.data.get("status")
        is_admin = request.data.get("is_admin")
        is_registered_directly = request.data.get("is_registered_directly")
        person_data = {
            "first_name": first_name,
            "middle_name": middle_name,
            "address": address,
            "out_of_address": out_of_address,
            "date_of_birth": date_of_birth,
            "blood_group": blood_group,
            "out_of_country": out_of_country,
            "flag_show": flag_show,
            "mobile_number1": mobile_number1,
            "mobile_number2": mobile_number2,
            "status": status_name,
            "surname": surname,
        }

        serializer = PersonSerializerV2(
            person, data=person_data, context={"person_id": person.id}
        )
        if serializer.is_valid():
            if len(children) > 0:
                children_exist = ParentChildRelation.objects.filter(child__in=children)
                if (
                    children_exist.exclude(parent=top_member)
                    .exclude(parent=person.id)
                    .exists()
                ):
                    return JsonResponse(
                        {"message": "Children already exist"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            persons = serializer.save()

            father_data = ParentChildRelation.objects.filter(child=persons.id)
            if father_data.exists():
                father_data.update(child=persons.id, parent=father)
            else:
                ParentChildRelation.objects.create(
                    child=persons.id, parent=father, created_user=admin_user_id
                )

            for child in children:
                child_data = ParentChildRelation.objects.filter(child=child)
                if child_data.exists():
                    child_data.update(parent=persons.id, child=child)
                else:
                    ParentChildRelation.objects.create(
                        child=child, parent=persons.id, created_user=admin_user_id
                    )

            if len(children) > 0:
                remove_child_person = ParentChildRelation.objects.filter(
                    parent=persons.id
                ).exclude(child__in=children)
                if remove_child_person.exists():
                    for child in remove_child_person:
                        child.update(parent_id=int(top_member))

            lang_data = TranslatePerson.objects.filter(person_id=persons.id).filter(
                language="guj"
            )
            if lang_data.exists():
                lang_data = lang_data.update(
                    first_name=guj_first_name,
                    middle_name=guj_middle_name,
                    address=guj_address,
                    out_of_address=guj_out_of_address,
                )
            else:
                lang_data = TranslatePerson.objects.create(
                    person_id=persons.id,
                    first_name=guj_first_name,
                    middle_name=guj_middle_name,
                    address=guj_address,
                    out_of_address=guj_out_of_address,
                    language=lang,
                )

            return Response(
                {"person": AdminPersonGetSerializer(persons, context={"lang": lang}).data},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, admin_user_id=None):
        if not admin_user_id:
            return Response(
                {"message": "Missing Admin User in request data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            admin_person = Person.objects.get(pk=admin_user_id)
        except Person.DoesNotExist:
            return Response(
                {"message": f"Admin Person not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if not admin_person.is_admin and not admin_person.is_super_admin:
            return Response(
                {"message": "User does not have admin access"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        person = get_object_or_404(Person, pk=pk)
        try:
            person.delete()
            return Response(
                {"message": f"Person record ID {pk} deleted successfully."},
                status=status.HTTP_204_NO_CONTENT,
            )
        except Exception as e:
            return Response(
                {"message": f"Failed to delete the person record with ID {pk}: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class V4CityDetailView(APIView):
    authentication_classes = []

    def get(self, request, state_id):
        try:
            state = State.objects.prefetch_related("state").get(id=state_id)
        except State.DoesNotExist:
            return Response(
                {"error": "State not found"}, status=status.HTTP_404_NOT_FOUND
            )
        state = state.state.all()
        lang = request.GET.get("lang", "en")
        serializer = CitySerializer(state, many=True, context={"lang": lang})
        city_list = serializer.data
        for index, instance in enumerate(city_list):
            if instance["id"] == 52:
                instance["sort_no"] = 0
            elif instance["id"] == 796:
                instance["sort_no"] = 1
            elif instance["id"] == 2:
                instance["sort_no"] = 2
            else:
                instance["sort_no"] = 3
        city_list = sorted(city_list, key=lambda x: (x["sort_no"], x["name"]))
        return Response(city_list, status=status.HTTP_200_OK)


class V4StateDetailView(APIView):
    authentication_classes = []

    def get(self, request):
        lang = request.GET.get("lang", "en")
        if lang == "guj":
            states = State.objects.all().order_by("guj_name")
        else:
            states = State.objects.all().order_by("name")
        serializer = StateSerializer(states, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)


class V4CountryDetailView(APIView):
    authentication_classes = []

    def get(self, request):
        country = Country.objects.all()
        lang = request.GET.get("lang", "en")
        serializer = CountrySerializer(country, many=True, context={"lang": lang})
        data = sorted(serializer.data, key=lambda x: (x["name"]))
        return Response(data, status=status.HTTP_200_OK)


class V4ChildPerson(APIView):
    def get(self, request):
        try:
            person_id = request.GET.get("parent_id")
            lang = request.GET.get("lang", "en")
            child_ids = ParentChildRelation.objects.filter(
                parent=int(person_id)
            ).values_list("child", flat=True)
            children = Person.objects.filter(id__in=child_ids, is_deleted=False)
            child_data = PersonGetSerializer(
                children, many=True, context={"lang": lang}
            )
            return Response({"child_data": child_data.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"child_data": [], "Error": e},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            parent_id = request.data.get("parent_id")
            lang = request.data.get("lang", "en")
            name = request.data.get("child_name")
            dob = request.data.get("dob")
            mobile_number = request.data.get("mobile_number") or ""
            platform = request.data.get("platform")
            person_data = Person.objects.get(id=parent_id, is_deleted=False)
            person_create = Person.objects.create(
                first_name=name,
                middle_name=person_data.first_name,
                surname=person_data.surname,
                date_of_birth=dob,
                address=person_data.address,
                mobile_number1=mobile_number,
                mobile_number2="",
                out_of_address=person_data.out_of_address,
                city=person_data.city,
                state=person_data.state,
                child_flag=True,
                platform=platform,
                update_field_message="newly created as child",
            )
            person_child = ParentChildRelation.objects.create(
                parent=person_data, child=person_create, created_user=person_data
            )
            try:
                translate_data = TranslatePerson.objects.get(
                    person_id=parent_id, is_deleted=False
                )
                if translate_data is not None:
                    TranslatePerson.objects.create(
                        person_id=person_create,
                        first_name=name,
                        middle_name=translate_data.first_name,
                        address=translate_data.address,
                        out_of_address=translate_data.out_of_address,
                        language="guj",
                    )
            except Exception:
                pass
            if lang == "guj":
                message = "તમારું બાળક સફળતાપૂર્વક અમારા સભ્યોમાં નોંધાયેલ છે. હવે તમે તમારા એડમિનનો સંપર્ક કરી શકો છો."
            else:
                message = "Your child is successfully registered in our members. Now you can contact your admin."
            return Response(
                {"message": message, "child_id": person_create.id},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request):
        try:
            child_id = request.data.get("child_id")
            child_name = request.data.get("child_name")
            dob = request.data.get("dob")
            mobile_number = request.data.get("mobile_number")
            lang = request.data.get("lang", "en")
            person_data = Person.objects.get(id=child_id)
            if person_data:
                ignore_fields = ["first_name", "date_of_birth", "mobile_number1"]
                update_field_message = []
                for field, new_value in request.data.items():
                    if field == "child_name":
                        field = "first_name"
                    elif field == "dob":
                        field = "date_of_birth"
                    elif field == "mobile_number":
                        field = "mobile_number1"
                    if field in ignore_fields:
                        old_value = getattr(person_data, field, None)
                        if hasattr(old_value, "id"):
                            old_value = old_value.id

                        if old_value != new_value:
                            update_field_message.append(
                                {"field": field, "previous": old_value, "new": new_value}
                            )

                if update_field_message:
                    person_data.update_field_message = str(update_field_message)

                existing_profile = person_data.profile
                person_data.first_name = child_name
                person_data.date_of_birth = dob
                person_data.mobile_number1 = mobile_number
                person_data.flag_show = False
                person_data.save()

                if "profile" in request.data:
                    new_profile = request.data["profile"]
                    person_data.profile = new_profile
                    person_data.save()

                if existing_profile and existing_profile != person_data.profile:
                    existing_profile.delete()

            return Response(
                {"child_id": child_id, "message": "succesfully updated"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request):
        try:
            lang = request.data.get("lang", "en")
            child_id = request.data.get("child_id")
            person = Person.objects.get(id=child_id)
            topmember = Surname.objects.get(id=person.surname.id)
            topmaember_id = topmember.top_member

            top_member_person = Person.objects.get(id=topmaember_id)

            parent_relation_data = ParentChildRelation.objects.filter(
                parent=person, is_deleted=False
            )
            if parent_relation_data:
                for data in parent_relation_data:
                    data.parent = top_member_person
                    data.save()

            relation_data = ParentChildRelation.objects.get(
                child=person, is_deleted=False
            )
            if relation_data:
                relation_data.is_deleted = True
                relation_data.save()

            person.flag_show = False
            person.is_deleted = True
            person.save()

            messages = {
                "deleted_data": {
                    "en": "Your child is successfully deleted in members",
                    "guj": "તમારા બાળકને સભ્યોમાંથી સફળતાપૂર્વક કાઢી નાખવામાં આવ્યું છે",
                },
            }
            return Response(
                {"message": messages["deleted_data"][lang]}, status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {"message": "Already Student Deleted"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


def V4updated_log(person_id, updated_history, created_person_id):
    try:
        person_instance = Person.objects.get(pk=person_id)
        created_person_instance = Person.objects.get(pk=created_person_id)

        PersonUpdateLog.objects.create(
            person=person_instance,
            updated_history=updated_history,
            created_person=created_person_instance,
        )
        return Response({"message": "okay"}, status=status.HTTP_200_OK)
    except Person.DoesNotExist:
        return Response(
            {"error": "Person instance not found"}, status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response({"error": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)


class V4ParentChildRelationDetailViewV3(APIView):
    def post(self, request):
        serializer = ParentChildRelationSerializer(data=request.data)
        if serializer.is_valid():
            parent_id = serializer.validated_data.get("parent_id")
            child_id = serializer.validated_data.get("child_id")
            try:
                existing_relation = ParentChildRelation.objects.get(
                    child_id=child_id, is_deleted=False
                )
                existing_relation.parent_id = parent_id
                existing_relation.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ParentChildRelation.DoesNotExist:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, surnameid=None):
        if surnameid:
            try:
                surnameid = int(surnameid)
            except ValueError:
                return Response(
                    {"error": "Invalid surname ID"}, status=status.HTTP_400_BAD_REQUEST
                )
            lang = request.GET.get("lang", "en")
            queryset = (
                Person.objects.filter(surname__id=surnameid, is_deleted=False)
                .order_by("date_of_birth")
                .annotate(
                    translated_first_name=Case(
                        When(
                            Q(
                                translateperson__first_name__isnull=False,
                                translateperson__language=lang,
                            ),
                            then=F("translateperson__first_name"),
                        ),
                        default=F("first_name"),
                    ),
                    translated_middle_name=Case(
                        When(
                            Q(
                                translateperson__middle_name__isnull=False,
                                translateperson__language=lang,
                            ),
                            then=F("translateperson__middle_name"),
                        ),
                        default=F("middle_name"),
                    ),
                )
                .select_related("surname")
                .prefetch_related("translateperson")
            )

            results = list(
                queryset.values(
                    "id",
                    "translated_first_name",
                    "translated_middle_name",
                    "date_of_birth",
                    "profile",
                    "thumb_profile",
                    "mobile_number1",
                    "mobile_number2",
                    "out_of_country",
                    "flag_show",
                    "emoji",
                )
            )

            total_count = len(results)
            relation_data = (
                ParentChildRelation.objects.filter(
                    Q(parent__surname__id=surnameid) & Q(child__surname__id=surnameid),
                    is_deleted=False,
                )
                .select_related("parent", "child")
                .order_by("parent__date_of_birth", "child__date_of_birth")
            )
            data2 = []
            if relation_data.exists():
                data = GetTreeRelationSerializer(relation_data, many=True).data
                if len(data) > 0:
                    surname_data = Surname.objects.filter(Q(id=int(surnameid)))
                    if surname_data.exists():
                        surname_data = surname_data.first()
                        top_member = int(
                            GetSurnameSerializer(surname_data).data.get("top_member", 0)
                        )
                        filtered_surname_results = filter(
                            lambda person: person["id"] == top_member, results
                        )
                        surname_relations = next(filtered_surname_results, None)
                        default_path = os.path.join(
                            settings.MEDIA_ROOT,
                            os.getenv("DEFAULT_PROFILE_PATH_WITHOUT_MEDIA", ""),
                        )
                        for j in data:
                            filtered_parent_results = filter(
                                lambda person: person["id"] == j["parent"], results
                            )
                            parent_relations = next(filtered_parent_results, None)
                            if parent_relations:
                                if (
                                    parent_relations["profile"] != "null"
                                    and parent_relations["profile"] != ""
                                ):
                                    file_path = os.path.join(
                                        settings.MEDIA_ROOT, parent_relations["profile"]
                                    )
                                    if not os.path.exists(file_path):
                                        parent_relations["profile"] = default_path
                                else:
                                    parent_relations["profile"] = default_path
                                if (
                                    parent_relations["thumb_profile"] != "null"
                                    and parent_relations["thumb_profile"] != ""
                                ):
                                    file_path = os.path.join(
                                        settings.MEDIA_ROOT,
                                        parent_relations["thumb_profile"],
                                    )
                                    if not os.path.exists(file_path):
                                        parent_relations["thumb_profile"] = default_path
                                else:
                                    parent_relations["thumb_profile"] = default_path
                            filtered_child_results = filter(
                                lambda person: person["id"] == j["child"], results
                            )
                            child_relations = next(filtered_child_results, None)
                            if child_relations:
                                if (
                                    child_relations["profile"] != "null"
                                    and child_relations["profile"] != ""
                                ):
                                    file_path = os.path.join(
                                        settings.MEDIA_ROOT, child_relations["profile"]
                                    )
                                    if not os.path.exists(file_path):
                                        child_relations["profile"] = default_path
                                else:
                                    child_relations["profile"] = default_path
                                if (
                                    child_relations["thumb_profile"] != "null"
                                    and child_relations["thumb_profile"] != ""
                                ):
                                    file_path = os.path.join(
                                        settings.MEDIA_ROOT,
                                        child_relations["thumb_profile"],
                                    )
                                    if not os.path.exists(file_path):
                                        child_relations["thumb_profile"] = default_path
                                else:
                                    child_relations["thumb_profile"] = default_path
                            if child_relations and child_relations["flag_show"] == True:
                                j["child"] = child_relations
                                j["parent"] = parent_relations
                                parent = j.get("parent")
                                flag_show = None
                                if parent and isinstance(parent, dict):
                                    flag_show = parent.get("flag_show")
                                if flag_show is not True:
                                    j["parent"] = surname_relations
                                data2.append(j)
            return Response(
                {"total_count": total_count, "data": data2}, status=status.HTTP_200_OK
            )
        else:
            return Response({"total_count": 0, "data": []}, status=status.HTTP_200_OK)

    def get_parent_child_relation(self, param, dictionary, lang):
        parent_child_relation = ParentChildRelation.objects.filter(
            Q(parent_id=param) | Q(child_id=param), is_deleted=False
        )
        if parent_child_relation:
            serializer = GetParentChildRelationSerializer(
                parent_child_relation, many=True, context={"lang": lang}
            )
            for child in serializer.data:
                tmp = None
                if len(dictionary) > 0:
                    for data in dictionary:
                        if int(child.get("child", None).get("id", None)) == int(
                            data.get("child", None).get("id", None)
                        ) and int(data.get("parent", None).get("id", None)) == int(
                            child.get("parent", None).get("id", None)
                        ):
                            tmp = data
                            break
                if not tmp:
                    dictionary.append(child)
                    self.get_parent_child_relation(
                        int(child.get("parent", None).get("id", None)), dictionary, lang
                    )
                    self.get_parent_child_relation(
                        int(child.get("child", None).get("id", None)), dictionary, lang
                    )

    def put(self, request, pk=None):
        created_user_id = request.data.get("created_user")
        lang = request.data.get("lang")
        if not created_user_id:
            return Response(
                {"error": "Admin Data not provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            created_user = Person.objects.get(id=created_user_id, is_deleted=False)
        except Person.DoesNotExist:
            return Response(
                {"error": "Admin member not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if not (created_user.is_admin or created_user.is_super_admin):
            return Response(
                {"error": "Permission denied: Only admins can edit this relation"},
                status=status.HTTP_403_FORBIDDEN,
            )
        parent_id = request.data.get("parent_id")
        if not parent_id:
            return Response(
                {"error": "Parent Data not provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            parent = Person.objects.get(id=parent_id, is_deleted=False)
        except Person.DoesNotExist:
            return Response(
                {"error": "Parent not found for this member."},
                status=status.HTTP_404_NOT_FOUND,
            )
        child_id = request.data.get("child_id")
        if not child_id:
            return Response(
                {"error": "Child Data not provided"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            child = Person.objects.get(id=child_id, is_deleted=False)
            if child:
                child.middle_name = parent.first_name
                child.save()
            try:
                parent_translate = TranslatePerson.objects.get(
                    person_id=parent_id, is_deleted=False
                )
                translate = TranslatePerson.objects.get(
                    person_id=child.id, is_deleted=False
                )
                if translate:
                    translate.middle_name = parent_translate.first_name
                    translate.save()
            except:
                pass
        except Person.DoesNotExist:
            return Response(
                {"error": "Child not found"}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            relation = ParentChildRelation.objects.get(child=child, is_deleted=False)
            if parent != child:
                try:
                    relation.parent = parent
                    relation.save()
                    return Response(
                        {
                            "message": "Your child is successfully moved under the "
                            + parent.first_name
                        },
                        status=status.HTTP_200_OK,
                    )
                except:
                    return Response(
                        {"message": "something is wrong"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
        except:
            pass
        return Response(
            {"message": "something is wrong"}, status=status.HTTP_403_FORBIDDEN
        )


class V4PersonBySurnameViewV3(APIView):
    def post(self, request):
        surname = request.data.get("surname")
        lang = request.data.get("lang", "en")
        is_father_selection = request.data.get("is_father_selection", "").lower()

        if not surname:
            message = "અટક જરૂરી છે" if lang == "guj" else "Surname ID is required"
            return JsonResponse({"message": message, "data": []}, status=status.HTTP_400_BAD_REQUEST)

        persons = (
            Person.objects.filter(surname__id=surname, is_deleted=False, flag_show=True)
            .exclude(
                id__in=Surname.objects.annotate(
                    top_member_as_int=Cast("top_member", IntegerField())
                ).values_list("top_member_as_int", flat=True)
            )
            .select_related("surname")
            .prefetch_related("translateperson")
            .distinct()
            .values(
                "id",
                "first_name",
                "translateperson__first_name",
                "middle_name",
                "translateperson__middle_name",
                "date_of_birth",
                "mobile_number1",
                "mobile_number2",
                "flag_show",
                "profile",
                "is_admin",
                "surname",
                "surname__name",
                "surname__guj_name",
                "thumb_profile",
            )
        )

        if is_father_selection != "true":
            persons = persons.filter(
                Q(mobile_number1__isnull=False) | Q(mobile_number2__isnull=False)
            ).exclude(mobile_number1="")

        if persons.exists():
            persons = (
                persons.order_by("first_name", "middle_name")
                if lang == "en"
                else persons.order_by(
                    "translateperson__first_name", "translateperson__middle_name"
                )
            )

            for person in persons:
                if lang != "en":
                    person["surname"] = person["surname__guj_name"]
                    (
                        person["first_name"],
                        person["middle_name"],
                        person["trans_first_name"],
                        person["trans_middle_name"],
                    ) = (
                        person["translateperson__first_name"],
                        person["translateperson__middle_name"],
                        person["first_name"],
                        person["middle_name"],
                    )
                else:
                    person["surname"] = person["surname__name"]
                    person["trans_first_name"], person["trans_middle_name"] = (
                        person["translateperson__first_name"],
                        person["translateperson__middle_name"],
                    )
                if (
                    person["profile"]
                    and person["profile"] != "null"
                    and person["profile"] != ""
                ):
                    person["profile"] = f"/media/{(person['profile'])}"
                else:
                    person["profile"] = os.getenv("DEFAULT_PROFILE_PATH")
                if (
                    person["thumb_profile"]
                    and person["thumb_profile"] != "null"
                    and person["thumb_profile"] != ""
                ):
                    person["thumb_profile"] = f"/media/{(person['thumb_profile'])}"
                else:
                    person["thumb_profile"] = os.getenv("DEFAULT_PROFILE_PATH")
                person.pop("translateperson__first_name")
                person.pop("translateperson__middle_name")
                person.pop("surname__name")
                person.pop("surname__guj_name")

            results = list(persons)
            return JsonResponse({"data": results}, status=status.HTTP_200_OK)

        return JsonResponse({"data": []}, status=status.HTTP_200_OK)


class V4PersonMiddleNameUpdate(APIView):
    def put(self, request):
        top_member_ids = Surname.objects.values("top_member").values_list(
            "top_member", flat=True
        )
        top_member_ids = [int(id) for id in top_member_ids]
        allChild = ParentChildRelation.objects.exclude(
            parent__id__in=top_member_ids, is_deleted=False
        ).order_by("id")
        if allChild and allChild.exists():
            for child in allChild:
                child.child.middle_name = child.parent.first_name
                child.child.save()

                traslate_child = TranslatePerson.objects.filter(
                    person_id=child.child, is_deleted=False
                ).first()
                traslate_parent = TranslatePerson.objects.filter(
                    person_id=child.parent, is_deleted=False
                ).first()
                if traslate_child and traslate_parent:
                    traslate_child.middle_name = traslate_parent.first_name
                    traslate_child.save()

        return JsonResponse({"data": "Okay"}, status=status.HTTP_200_OK)


class V4SearchbyPerson(APIView):
    def post(self, request):
        lang = request.data.get("lang", "en")
        search = request.data.get("search", "")
        # isAllSearch = request.data.get("is_all_search", "false")
        if search == "":
            return JsonResponse({"data": []}, status=status.HTTP_200_OK)

        search_keywords = search.split(" ")
        query = Q()
        for keyword in search_keywords:
            query &= (
                Q(first_name__icontains=keyword)
                | Q(date_of_birth__icontains=keyword)
                | Q(mobile_number1__icontains=keyword)
                | Q(mobile_number2__icontains=keyword)
                | Q(surname__name__icontains=keyword)
                | Q(surname__guj_name__icontains=keyword)
                | Q(translateperson__first_name__icontains=keyword)
            )

        query = Person.objects.filter(query, flag_show=True, is_deleted=False).exclude(
            id__in=Surname.objects.annotate(
                top_member_as_int=Cast("top_member", IntegerField())
            ).values_list("top_member_as_int", flat=True)
        )

        query = (
            query.select_related("surname")
            .distinct()
            .order_by(
                "first_name",
                "translateperson__first_name",
                "middle_name",
                "translateperson__middle_name",
                "surname__name",
            )
        )

        data = PersonGetDataSortSerializer(query, many=True, context={"lang": lang})
        return JsonResponse({"data": data.data}, status=status.HTTP_200_OK)


def V4getadmincontact(flag_show=False, lang="en", surname=None):
    if flag_show == False:
        admin = None
        if surname is not None:
            if lang == "guj":
                admin = Person.objects.filter(
                    surname__guj_name=surname,
                    flag_show=True,
                    is_admin=True,
                    is_deleted=False,
                )
            else:
                admin = Person.objects.filter(
                    surname__name=surname,
                    flag_show=True,
                    is_admin=True,
                    is_deleted=False,
                )
        if admin and admin.exists():
            admin_serializer = PersonGetSerializer(
                admin, context={"lang": lang}, many=True
            )
            admin_data = admin_serializer.data
        else:
            admin_data = []

        super_admin = Person.objects.filter(
            flag_show=True, is_super_admin=True, is_deleted=False
        )
        admin_serializer1 = PersonGetSerializer(
            super_admin, context={"lang": lang}, many=True
        )
        super_admin_data = admin_serializer1.data
        combined_data = sorted(
            super_admin_data,
            key=lambda x: (
                x["surname"],
                x["first_name"],
            ),
        )
        combined_data = sorted(
            combined_data,
            key=lambda x: (x["surname"] != surname, x["surname"], x["first_name"]),
        )

        if lang == "guj":
            error_message = (
                "તમારી નવા સભ્ય માં નોંધણી થઈ ગઈ છે. હવે તમે કૃપા કરી ને કાર્યકર્તાને સંપર્ક કરો."
            )
        else:
            error_message = "You are successfully registered as one of our members. Now you can contact your admin."

        return {
            "message": error_message,
            "admin_data": admin_data + combined_data,
        }

    return {"message": "", "admin_data": []}


class V4AdditionalData(APIView):
    def get(self, request):
        additional_data_entry = AdsSetting.objects.values("ads_setting").first()
        additional_data = (
            additional_data_entry["ads_setting"] if additional_data_entry else {}
        )
        return Response({"additional_data": additional_data}, status=status.HTTP_200_OK)


class V4V3SurnameDetailView(APIView):
    authentication_classes = []

    def get(self, request):
        person_id = request.GET.get("person_id")
        lang = request.GET.get("lang", "en")
        try:
            person = Person.objects.get(id=person_id, is_deleted=False)
        except:
            return Response(
                {"message": "Person Not Found"}, status=status.HTTP_404_NOT_FOUND
            )

        surnames = Surname.objects.all().order_by("fix_order")
        serializer = SurnameSerializer(surnames, many=True, context={"lang": lang})
        surname_data = serializer.data
        for index, instance in enumerate(surname_data):
            if instance["id"] == person.surname.id:
                instance["sort_no"] = 0
            else:
                instance["sort_no"] = 2
        surname_data = sorted(surname_data, key=lambda x: (x["sort_no"]))
        return Response(surname_data, status=status.HTTP_200_OK)

    def post(self, request):
        surname_serializer = SurnameSerializer(data=request.data)
        if surname_serializer.is_valid():
            surname_instance = surname_serializer.save()
            person_data = {
                "first_name": surname_instance.name,
                "middle_name": surname_instance.name,
                "address": "",
                "blood_group": 1,
                "date_of_birth": "1947-08-15 00:00:00.000",
                "out_of_country": 1,
                "out_of_address": "",
                "city": 1,
                "state": 1,
                "mobile_number1": "",
                "mobile_number2": "",
                "surname": surname_instance.id,
                "flag_show": True,
                "is_admin": False,
                "is_registered_directly": True,
            }
            person_serializer = PersonSerializer(data=person_data)
            if person_serializer.is_valid():
                person_instance = person_serializer.save()
                surname_instance.top_member = person_instance.id
                surname_instance.save()
                lang = request.data.get("lang", "en")
                if lang != "en":
                    guj_name = request.data.get(
                        "guj_name", request.data.get("name", "")
                    )
                    if guj_name:
                        person_translate_data = {
                            "first_name": guj_name,
                            "person_id": person_instance.id,
                            "middle_name": guj_name,
                            "address": "",
                            "out_of_address": "",
                            "language": lang,
                        }
                        person_translate_serializer = TranslatePersonSerializer(
                            data=person_translate_data
                        )
                        if person_translate_serializer.is_valid():
                            person_translate_serializer.save()
                            return Response(
                                {"surname": surname_serializer.data},
                                status=status.HTTP_201_CREATED,
                            )
                        else:
                            surname_instance.delete()
                            person_instance.delete()
                            return Response(
                                person_translate_serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                return Response(
                    {"surname": surname_serializer.data}, status=status.HTTP_201_CREATED
                )
            else:
                surname_instance.delete()
                return Response(
                    person_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )
        return Response(surname_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def V4append_to_log(filename, message):
    with open(filename, "a") as file:
        file.write(message + "\n")


class V4V3BannerDetailView(APIView):
    def get(self, request):
        today = datetime.now().date()
        Banner.objects.filter(
            expire_date__lt=today, is_active=True, is_deleted=False
        ).update(is_active=False)
        active_banner = Banner.objects.filter(
            is_active=True, expire_date__gte=today, is_deleted=False
        ).order_by("expire_date")
        expire_banner = Banner.objects.filter(
            is_active=False, expire_date__lt=today, is_deleted=False
        ).order_by("-expire_date")

        active_banner_data = BannerGETSerializer(active_banner, many=True).data
        expire_banner_data = BannerGETSerializer(expire_banner, many=True).data
        is_random_banner = RandomBanner.objects.values_list(
            "is_random_banner", flat=True
        ).first()

        return Response(
            {
                "is_random_banner": is_random_banner,
                "Current Banner": active_banner_data,
                "Expire Banner": expire_banner_data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        today = datetime.now().date()
        images = request.FILES.getlist("images")
        created_person = int(request.data.get("created_person"))
        person = get_object_or_404(Person, id=created_person).id
        expire_days = request.data.get("expire_days", 0)
        is_ad_lable = True
        if "is_ad_lable" in request.data:
            is_ad_lable = request.data.get("is_ad_lable").lower()
            if is_ad_lable == "true":
                is_ad_lable = True
            else:
                is_ad_lable = False

        if not expire_days:
            return Response(
                {"message": "Please enter expire_days"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            expire_days = int(expire_days)
        except ValueError:
            return Response(
                {"message": "Please enter a valid number for expire_days"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(images) != 1:
            return Response(
                {"message": "Please upload exactly one image"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expire_date = today + timedelta(days=expire_days)

        serializer = BannerSerializer(
            data={
                "images": images[0],
                "redirect_url": request.data.get("redirect_url"),
                "expire_date": expire_date,
                "created_person": person,
                "is_ad_lable": is_ad_lable,
            }
        )

        try:
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request):
        banner_id = request.data.get("banner_id")
        if not banner_id:
            return Response(
                {"message": "Please enter Banner Details"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        banner = get_object_or_404(Banner, id=banner_id)
        images = request.FILES.getlist("images")
        expire_days = request.data.get("expire_days", 0)
        redirect_url = request.data.get("redirect_url")
        if images:
            if len(images) != 1:
                return Response(
                    {"message": "Please upload exactly one image"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            banner.images = images[0]

        if redirect_url is not None:
            banner.redirect_url = redirect_url

        if expire_days:
            try:
                expire_days = int(expire_days)
                banner.expire_date = datetime.now().date() + timedelta(days=expire_days)
                banner.is_active = True
            except ValueError:
                return Response(
                    {"message": "Please enter a valid number for expire_days"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if "is_ad_lable" in request.data:
            is_ad_lable = request.data.get("is_ad_lable").lower()
            if is_ad_lable == "true":
                is_ad_lable = True
            else:
                is_ad_lable = False
            banner.is_ad_lable = is_ad_lable

        try:
            banner.save()
            return Response({"message": "Your Banner Data is Successfully Updated"}, status=status.HTTP_200_OK)
        except Exception as error:
            return Response({"message": str(error)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            banner = get_object_or_404(Banner, pk=pk)
            if banner.is_deleted == False:
                banner.is_active = False
                banner.is_deleted = True
                banner.save()
                return Response(
                    {"message": f"Banner record ID {pk} deleted successfully."},
                    status=status.HTTP_204_NO_CONTENT,
                )
            else:
                return Response(
                    {"message": f"Banner record ID {pk} already deleted."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except Exception as e:
            return Response(
                {
                    "message": f"Failed to delete the Banner record with ID {pk}: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class V4RandomBannerView(APIView):
    def post(self, request):
        is_random_banner = False
        if "is_random_banner" in request.data:
            is_random_banner = request.data.get("is_random_banner").lower()
            if is_random_banner == "true":
                is_random_banner = True
            else:
                is_random_banner = False
        try:
            data = RandomBanner.objects.all().first()
            if data:
                data.is_random_banner = is_random_banner
                data.save()
                return Response(
                    {"message": "data Successfully updated"}, status=status.HTTP_200_OK
                )
            else:
                RandomBanner.objects.create(is_random_banner=is_random_banner)
                return Response(
                    {"message": "data Successfully created"},
                    status=status.HTTP_201_CREATED,
                )
        except Exception as error:
            return Response({"message": f"{error}"}, status=status.HTTP_400_BAD_REQUEST)


def V4capitalize_name(name):
    return name.capitalize()


class V4FirstCapitalize(APIView):
    def get(self, request):
        person = Person.objects.all()
        for i in person:
            i.first_name = V4capitalize_name(i.first_name)
            i.middle_name = V4capitalize_name(i.middle_name)
            i.save()
        return Response({"okay"}, status=status.HTTP_200_OK)
