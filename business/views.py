from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q, Count, F
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from business.models import (
    BusinessCategory,
    BusinessSubCategory,
    Business,
    BusinessOwner,
    BusinessImage,
    BusinessSearchHistory,
    SearchIntent,
    SearchInterest
)
from business.serializers import (
    BusinessCategorySerializer,
    BusinessSubCategorySerializer,
    BusinessListSerializer,
    BusinessDetailSerializer,
    BusinessCreateUpdateSerializer,
    BusinessOwnerSerializer,
    BusinessImageSerializer,
    BusinessSearchHistorySerializer,
    SearchIntentSerializer,
    SearchInterestSerializer
)


class BusinessCategoryListView(APIView):
    """Get all active business categories"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get all active business categories",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Categories list", schema=BusinessCategorySerializer(many=True))}
    )
    def get(self, request):
        lang = request.GET.get('lang', 'en')
        categories = BusinessCategory.objects.filter(is_active=True)
        serializer = BusinessCategorySerializer(categories, many=True, context={'lang': lang, 'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class BusinessCategoryDetailView(APIView):
    """Get single category details"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get single category details by ID",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={
            200: openapi.Response(description="Category details", schema=BusinessCategorySerializer()),
            404: "Category not found"
        }
    )
    def get(self, request, pk):
        lang = request.GET.get('lang', 'en')
        try:
            category = BusinessCategory.objects.get(pk=pk, is_active=True)
            serializer = BusinessCategorySerializer(category, context={'lang': lang, 'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except BusinessCategory.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)


class BusinessCategoryWithCountsView(APIView):
    """Get categories with business counts"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get categories with business counts and subcategories",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING),
            openapi.Parameter('include_subcategories', openapi.IN_QUERY, description="Include subcategories (default: true)", type=openapi.TYPE_BOOLEAN),
        ],
        responses={200: "Categories with business_count field and subcategories"}
    )
    def get(self, request):
        lang = request.GET.get('lang', 'en')
        categories = BusinessCategory.objects.filter(is_active=True).prefetch_related('subcategories').annotate(
            business_count=Count('businesses', filter=Q(businesses__is_active=True, businesses__is_deleted=False))
        )
        serializer = BusinessCategorySerializer(categories, many=True, context={'lang': lang, 'request': request})
        data = serializer.data
        
        # Add business counts
        for i, category in enumerate(categories):
            data[i]['business_count'] = category.business_count
        
        return Response(data, status=status.HTTP_200_OK)


class SubCategoryListView(APIView):
    """Get all subcategories for a specific category"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get all active subcategories for a category",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, type=openapi.TYPE_STRING, description='Language (en/guj)'),
        ],
        responses={
            200: openapi.Response(description="Subcategories list", schema=BusinessSubCategorySerializer(many=True)),
            404: "Category not found"
        }
    )
    def get(self, request, category_id):
        try:
            category = BusinessCategory.objects.get(id=category_id, is_active=True)
        except BusinessCategory.DoesNotExist:
            return Response(
                {"error": "Category not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        subcategories = BusinessSubCategory.objects.filter(
            category=category,
            is_active=True
        ).order_by('display_order', 'name')
        
        serializer = BusinessSubCategorySerializer(
            subcategories,
            many=True,
            context={'request': request}
        )
        
        return Response({
            "category": {
                "id": category.id,
                "name": category.name,
                "guj_name": category.guj_name
            },
            "subcategories": serializer.data
        }, status=status.HTTP_200_OK)


class SubCategoryDetailView(APIView):
    """Get single subcategory details"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get subcategory details",
        responses={
            200: openapi.Response(description="Subcategory details", schema=BusinessSubCategorySerializer()),
            404: "Subcategory not found"
        }
    )
    def get(self, request, pk):
        try:
            subcategory = BusinessSubCategory.objects.get(id=pk, is_active=True)
        except BusinessSubCategory.DoesNotExist:
            return Response(
                {"error": "Subcategory not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = BusinessSubCategorySerializer(
            subcategory,
            context={'request': request}
        )
        
        return Response(serializer.data, status=status.HTTP_200_OK)


class BusinessListView(APIView):
    """List and create businesses"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="List all businesses with filters and pagination",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Items per page (default: 20)", type=openapi.TYPE_INTEGER),
            openapi.Parameter('category', openapi.IN_QUERY, description="Filter by category ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('subcategory', openapi.IN_QUERY, description="Filter by subcategory ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('village', openapi.IN_QUERY, description="Filter by village ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('verified', openapi.IN_QUERY, description="Filter by verified status (true/false)", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('order_by', openapi.IN_QUERY, description="Order by field (default: -created_at)", type=openapi.TYPE_STRING),
        ],
        responses={200: "Paginated business list"}
    )
    def get(self, request):
        lang = request.GET.get('lang', 'en')
        page_num = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        # Build queryset
        businesses = Business.objects.filter(is_deleted=False, is_active=True)
        
        # Filters
        category = request.GET.get('category')
        if category:
            businesses = businesses.filter(category_id=category)
        
        # NEW: Subcategory filter
        subcategory = request.GET.get('subcategory')
        if subcategory:
            businesses = businesses.filter(subcategory_id=subcategory)
        
        village = request.GET.get('village')
        if village:
            businesses = businesses.filter(village_id=village)
        
        verified = request.GET.get('verified')
        if verified is not None:
            businesses = businesses.filter(is_verified=verified.lower() == 'true')
        
        # Prefetch related (added subcategory)
        businesses = businesses.select_related('category', 'subcategory', 'village', 'taluka', 'district', 'state').prefetch_related('owners_set', 'images')
        
        # Ordering
        order_by = request.GET.get('order_by', '-created_at')
        businesses = businesses.order_by(order_by)
        
        # Pagination
        paginator = Paginator(businesses, page_size)
        page_obj = paginator.get_page(page_num)
        
        serializer = BusinessListSerializer(page_obj.object_list, many=True, context={'lang': lang, 'request': request})
        
        return Response({
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_num,
            'results': serializer.data
        }, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_description="Create new business",
        request_body=BusinessCreateUpdateSerializer,
        responses={
            201: openapi.Response(description="Business created", schema=BusinessDetailSerializer()),
            400: "Validation error"
        }
    )
    def post(self, request):
        """Create new business"""
        serializer = BusinessCreateUpdateSerializer(data=request.data, context={'request': request, 'lang': request.GET.get('lang', 'en')})
        if serializer.is_valid():
            business = serializer.save()
            detail_serializer = BusinessDetailSerializer(business, context={'request': request, 'lang': request.GET.get('lang', 'en')})
            return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BusinessDetailView(APIView):
    """Get, update, delete business"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get business details by ID (increments view count)",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={
            200: openapi.Response(description="Business details", schema=BusinessDetailSerializer()),
            404: "Business not found"
        }
    )
    def get(self, request, pk):
        lang = request.GET.get('lang', 'en')
        try:
            business = Business.objects.select_related('category', 'village', 'taluka', 'district', 'state').prefetch_related('owners_set', 'images', 'translations').get(pk=pk, is_deleted=False)
            
            # Increment view count
            business.views_count = F('views_count') + 1
            business.save(update_fields=['views_count'])
            business.refresh_from_db()
            
            serializer = BusinessDetailSerializer(business, context={'lang': lang, 'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        operation_description="Update business (only owners can update)",
        request_body=BusinessCreateUpdateSerializer,
        responses={
            200: openapi.Response(description="Business updated", schema=BusinessDetailSerializer()),
            403: "Only owners can update business",
            404: "Business not found"
        }
    )
    def put(self, request, pk):
        """Update business"""
        lang = request.GET.get('lang', 'en')
        try:
            business = Business.objects.get(pk=pk, is_deleted=False)
            
            # Check if user is owner
            if not hasattr(request.user, 'person'):
                return Response({'error': 'User does not have a person profile'}, status=status.HTTP_400_BAD_REQUEST)
            
            is_owner = business.owners_set.filter(person=request.user.person).exists()
            if not is_owner:
                return Response({'error': 'Only owners can update business'}, status=status.HTTP_403_FORBIDDEN)
            
            serializer = BusinessCreateUpdateSerializer(business, data=request.data, context={'request': request, 'lang': lang})
            if serializer.is_valid():
                serializer.save()
                detail_serializer = BusinessDetailSerializer(business, context={'request': request, 'lang': lang})
                return Response(detail_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        operation_description="Partial update business (only owners can update)",
        request_body=BusinessCreateUpdateSerializer,
        responses={
            200: openapi.Response(description="Business updated", schema=BusinessDetailSerializer()),
            403: "Only owners can update business",
            404: "Business not found"
        }
    )
    def patch(self, request, pk):
        """Partial update business"""
        return self.put(request, pk)
    
    @swagger_auto_schema(
        operation_description="Soft delete business (only primary owner can delete)",
        responses={
            204: "Business deleted successfully",
            403: "Only primary owner can delete business",
            404: "Business not found"
        }
    )
    def delete(self, request, pk):
        """Soft delete business"""
        try:
            business = Business.objects.get(pk=pk, is_deleted=False)
            
            # Check if user is primary owner
            if not hasattr(request.user, 'person'):
                return Response({'error': 'User does not have a person profile'}, status=status.HTTP_400_BAD_REQUEST)
            
            is_primary = business.owners_set.filter(person=request.user.person, role='PRIMARY').exists()
            if not is_primary:
                return Response({'error': 'Only primary owner can delete business'}, status=status.HTTP_403_FORBIDDEN)
            
            business.is_deleted = True
            business.deleted_at = timezone.now()
            business.save()
            
            return Response({'message': 'Business deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)


class MyBusinessesView(APIView):
    """Get all businesses owned by authenticated user"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get all businesses owned by authenticated user",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Items per page (default: 20)", type=openapi.TYPE_INTEGER),
        ],
        responses={200: "Paginated list of user's businesses"}
    )
    def get(self, request):
        lang = request.GET.get('lang', 'en')
        page_num = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        if not hasattr(request.user, 'person'):
            return Response({'error': 'User does not have a person profile'}, status=status.HTTP_400_BAD_REQUEST)
        
        businesses = Business.objects.filter(
            owners=request.user.person,
            is_deleted=False
        ).select_related('category', 'village').prefetch_related('owners_set', 'images').order_by('-created_at')
        
        # Pagination
        paginator = Paginator(businesses, page_size)
        page_obj = paginator.get_page(page_num)
        
        serializer = BusinessListSerializer(page_obj.object_list, many=True, context={'lang': lang, 'request': request})
        
        return Response({
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_num,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class BusinessListByPersonView(APIView):
    """Get businesses by person ID"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get businesses by person ID (shows all if own profile, only verified if others)",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Items per page (default: 20)", type=openapi.TYPE_INTEGER),
        ],
        responses={200: "Paginated list of person's businesses with role info"}
    )
    def get(self, request, person_id):
        lang = request.GET.get('lang', 'en')
        page_num = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        if not hasattr(request.user, 'person'):
            return Response({'error': 'User does not have a person profile'}, status=status.HTTP_400_BAD_REQUEST)
        
        is_own_profile = str(request.user.person.id) == str(person_id)
        
        businesses = Business.objects.filter(
            owners__id=person_id,
            is_deleted=False
        )
        
        # Only show verified businesses if viewing other's profile
        if not is_own_profile:
            businesses = businesses.filter(is_verified=True)
        
        businesses = businesses.select_related('category', 'village').prefetch_related('owners_set', 'images').order_by('-created_at')
        
        # Pagination
        paginator = Paginator(businesses, page_size)
        page_obj = paginator.get_page(page_num)
        
        serializer = BusinessListSerializer(page_obj.object_list, many=True, context={'lang': lang, 'request': request})
        data = serializer.data
        
        # Add is_primary_owner and role
        for i, business in enumerate(page_obj.object_list):
            owner = business.owners_set.filter(person_id=person_id).first()
            if owner:
                data[i]['is_primary_owner'] = owner.role == 'PRIMARY'
                data[i]['role'] = owner.role
        
        return Response({
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_num,
            'results': data
        }, status=status.HTTP_200_OK)


class BusinessSearchView(APIView):
    """Search businesses with keyword matching"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Search businesses with keyword matching and synonym expansion",
        manual_parameters=[
            openapi.Parameter('q', openapi.IN_QUERY, description="Search query (required)", type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Items per page (default: 20)", type=openapi.TYPE_INTEGER),
            openapi.Parameter('category', openapi.IN_QUERY, description="Filter by category ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('village', openapi.IN_QUERY, description="Filter by village ID", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: "Paginated search results",
            400: "Search query is required"
        }
    )
    def get(self, request):
        lang = request.GET.get('lang', 'en')
        query = request.GET.get('q', '').strip()
        page_num = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        if not query:
            return Response({'error': 'Search query is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Track search history
        if hasattr(request.user, 'person'):
            BusinessSearchHistory.objects.create(
                person=request.user.person,
                keyword=query
            )
            
            # Update search interest
            village = request.GET.get('village')
            village_id = int(village) if village else None
            
            interest, created = SearchInterest.objects.get_or_create(
                keyword=query.lower(),
                village_id=village_id
            )
            if not created:
                interest.search_count = F('search_count') + 1
                interest.save()
        
        # Expand query with synonyms
        expanded_terms = [query.lower()]
        intent = SearchIntent.objects.filter(keyword__iexact=query, is_active=True).first()
        if intent:
            expanded_terms.extend(intent.get_related_terms_list())
        
        # Build search query
        q_objects = Q()
        for term in expanded_terms:
            q_objects |= Q(title__icontains=term)
            q_objects |= Q(description__icontains=term)
            q_objects |= Q(keywords__icontains=term)
        
        businesses = Business.objects.filter(
            q_objects,
            is_active=True,
            is_deleted=False
        )
        
        # Apply filters
        category = request.GET.get('category')
        if category:
            businesses = businesses.filter(category_id=category)
        
        village = request.GET.get('village')
        if village:
            businesses = businesses.filter(village_id=village)
        
        businesses = businesses.select_related('category', 'village').prefetch_related('owners_set', 'images').distinct().order_by('-created_at')
        
        # Pagination
        paginator = Paginator(businesses, page_size)
        page_obj = paginator.get_page(page_num)
        
        serializer = BusinessListSerializer(page_obj.object_list, many=True, context={'lang': lang, 'request': request})
        
        return Response({
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_num,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class AddBusinessOwnerView(APIView):
    """Add owner to business"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Add owner to business (only primary owner can add)",
        request_body=BusinessOwnerSerializer,
        responses={
            201: openapi.Response(description="Owner added", schema=BusinessOwnerSerializer()),
            403: "Only primary owner can add owners",
            404: "Business not found"
        }
    )
    def post(self, request, pk):
        try:
            business = Business.objects.get(pk=pk, is_deleted=False)
            
            # Check if user is primary owner
            if not hasattr(request.user, 'person'):
                return Response({'error': 'User does not have a person profile'}, status=status.HTTP_400_BAD_REQUEST)
            
            is_primary = business.owners_set.filter(person=request.user.person, role='PRIMARY').exists()
            if not is_primary:
                return Response({'error': 'Only primary owner can add owners'}, status=status.HTTP_403_FORBIDDEN)
            
            serializer = BusinessOwnerSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                serializer.save(business=business)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)


class RemoveBusinessOwnerView(APIView):
    """Remove owner from business"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Remove owner from business (only primary owner can remove, cannot remove primary owner)",
        responses={
            204: "Owner removed successfully",
            400: "Cannot remove primary owner",
            403: "Only primary owner can remove owners",
            404: "Business or owner not found"
        }
    )
    def delete(self, request, pk, owner_id):
        try:
            business = Business.objects.get(pk=pk, is_deleted=False)
            
            # Check if user is primary owner
            if not hasattr(request.user, 'person'):
                return Response({'error': 'User does not have a person profile'}, status=status.HTTP_400_BAD_REQUEST)
            
            is_primary = business.owners_set.filter(person=request.user.person, role='PRIMARY').exists()
            if not is_primary:
                return Response({'error': 'Only primary owner can remove owners'}, status=status.HTTP_403_FORBIDDEN)
            
            try:
                owner = BusinessOwner.objects.get(id=owner_id, business=business)
                
                # Cannot remove primary owner
                if owner.role == 'PRIMARY':
                    return Response({'error': 'Cannot remove primary owner'}, status=status.HTTP_400_BAD_REQUEST)
                
                owner.delete()
                return Response({'message': 'Owner removed successfully'}, status=status.HTTP_204_NO_CONTENT)
            
            except BusinessOwner.DoesNotExist:
                return Response({'error': 'Owner not found'}, status=status.HTTP_404_NOT_FOUND)
        
        except Business.DoesNotExist:
            return Response({'error': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)


class UploadBusinessImageView(APIView):
    """Upload image to business"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Upload image to business (only owners can upload)",
        request_body=BusinessImageSerializer,
        responses={
            201: openapi.Response(description="Image uploaded", schema=BusinessImageSerializer()),
            403: "Only owners can upload images",
            404: "Business not found"
        }
    )
    def post(self, request, pk):
        try:
            business = Business.objects.get(pk=pk, is_deleted=False)
            
            # Check if user is owner
            if not hasattr(request.user, 'person'):
                return Response({'error': 'User does not have a person profile'}, status=status.HTTP_400_BAD_REQUEST)
            
            is_owner = business.owners_set.filter(person=request.user.person).exists()
            if not is_owner:
                return Response({'error': 'Only owners can upload images'}, status=status.HTTP_403_FORBIDDEN)
            
            serializer = BusinessImageSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                serializer.save(business=business)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)


class SearchHistoryListView(APIView):
    """Get user's search history"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get authenticated user's search history",
        manual_parameters=[
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Items per page (default: 20)", type=openapi.TYPE_INTEGER),
        ],
        responses={200: "Paginated search history"}
    )
    def get(self, request):
        if not hasattr(request.user, 'person'):
            return Response({'error': 'User does not have a person profile'}, status=status.HTTP_400_BAD_REQUEST)
        
        page_num = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        history = BusinessSearchHistory.objects.filter(
            person=request.user.person
        ).order_by('-searched_at')
        
        # Pagination
        paginator = Paginator(history, page_size)
        page_obj = paginator.get_page(page_num)
        
        serializer = BusinessSearchHistorySerializer(page_obj.object_list, many=True)
        
        return Response({
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_num,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class TopKeywordsView(APIView):
    """Get user's top searched keywords"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get user's top 3 searched keywords (last 30 days)",
        responses={200: "List of top keywords with counts"}
    )
    def get(self, request):
        if not hasattr(request.user, 'person'):
            return Response({'error': 'User does not have a person profile'}, status=status.HTTP_400_BAD_REQUEST)
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        top_keywords = BusinessSearchHistory.objects.filter(
            person=request.user.person,
            searched_at__gte=thirty_days_ago
        ).values('normalized_keyword').annotate(
            count=Count('id')
        ).order_by('-count')[:3]
        
        return Response(list(top_keywords), status=status.HTTP_200_OK)


class TrendingSearchesView(APIView):
    """Get trending searches"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get trending searches (optionally filtered by village)",
        manual_parameters=[
            openapi.Parameter('village', openapi.IN_QUERY, description="Filter by village ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('limit', openapi.IN_QUERY, description="Number of results (default: 10)", type=openapi.TYPE_INTEGER),
        ],
        responses={200: openapi.Response(description="Trending searches", schema=SearchInterestSerializer(many=True))}
    )
    def get(self, request):
        village = request.GET.get('village')
        limit = int(request.GET.get('limit', 10))
        
        interests = SearchInterest.objects.all()
        
        if village:
            interests = interests.filter(village_id=village)
        
        interests = interests.order_by('-search_count', '-last_searched_at')[:limit]
        
        serializer = SearchInterestSerializer(interests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

