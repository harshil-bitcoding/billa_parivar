from rest_framework import serializers
from business.models import (
    BusinessCategory,
    BusinessSubCategory,
    Business,
    BusinessOwner,
    TranslateBusiness,
    BusinessImage,
    BusinessSearchHistory,
    SearchIntent,
    SearchInterest
)
from parivar.models import Person




class BusinessSubCategorySerializer(serializers.ModelSerializer):
    """Serializer for business subcategories with multi-language support"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    business_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessSubCategory
        fields = [
            'id', 'category', 'category_name', 'name', 'guj_name', 
            'icon', 'is_active', 'display_order', 'business_count'
        ]
    
    def get_business_count(self, obj):
        """Count active businesses in this subcategory"""
        return obj.businesses.filter(is_active=True, is_deleted=False).count()
    
    def to_representation(self, instance):
        """Add language-specific name based on request"""
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and request.query_params.get('lang') == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        return data


class BusinessCategorySerializer(serializers.ModelSerializer):
    """Serializer for business categories with multi-language support"""
    
    subcategories = BusinessSubCategorySerializer(many=True, read_only=True)
    business_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessCategory
        fields = ['id', 'name', 'guj_name', 'icon', 'is_active', 'display_order', 'subcategories', 'business_count']
    
    def get_business_count(self, obj):
        """Count businesses in category (including subcategories)"""
        return obj.businesses.filter(is_active=True, is_deleted=False).count()
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        # Language support
        lang = request.query_params.get('lang', 'en') if request else 'en'
        if lang == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        
        # Optionally exclude subcategories for list views
        if request and request.query_params.get('include_subcategories') == 'false':
            data.pop('subcategories', None)
        
        return data



class PersonMinimalSerializer(serializers.ModelSerializer):
    """Minimal person info for owner details"""
    surname_name = serializers.CharField(source='surname.name', read_only=True)
    profile_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Person
        fields = ['id', 'first_name', 'surname_name', 'mobile_number1', 'profile_url']
    
    def get_profile_url(self, obj):
        if obj.profile:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile.url)
            return obj.profile.url
        return None


class BusinessOwnerSerializer(serializers.ModelSerializer):
    """Serializer for business owners (registered and external)"""
    person = PersonMinimalSerializer(read_only=True)
    display_name = serializers.CharField(read_only=True)
    contact_number = serializers.CharField(read_only=True)
    
    # Write-only fields for creating owners
    person_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = BusinessOwner
        fields = [
            'id', 'person', 'person_id', 'name', 'mobile',
            'display_name', 'contact_number', 'role', 'owner_type',
            'is_active', 'added_at'
        ]
        read_only_fields = ['id', 'owner_type', 'display_name', 'contact_number', 'added_at']
    
    def validate(self, data):
        """Validate that either person_id or (name + mobile) is provided"""
        person_id = data.get('person_id')
        name = data.get('name')
        mobile = data.get('mobile')
        
        if not person_id and (not name or not mobile):
            raise serializers.ValidationError(
                "Either person_id or both name and mobile must be provided"
            )
        
        return data
    
    def create(self, validated_data):
        person_id = validated_data.pop('person_id', None)
        
        if person_id:
            validated_data['person_id'] = person_id
        
        return super().create(validated_data)


class BusinessImageSerializer(serializers.ModelSerializer):
    """Serializer for business images with thumbnail support"""
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessImage
        fields = ['id', 'image', 'image_url', 'thumbnail', 'thumbnail_url', 'is_primary', 'display_order', 'uploaded_at']
        read_only_fields = ['id', 'thumbnail', 'uploaded_at']
    
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
    
    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None


class TranslateBusinessSerializer(serializers.ModelSerializer):
    """Serializer for business translations"""
    
    class Meta:
        model = TranslateBusiness
        fields = ['id', 'language', 'title', 'description', 'is_deleted']


class BusinessListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for business list views"""
    category = BusinessCategorySerializer(read_only=True)
    subcategory = BusinessSubCategorySerializer(read_only=True)
    primary_owner = serializers.SerializerMethodField()
    owners_count = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    primary_image_url = serializers.SerializerMethodField()
    village_name = serializers.CharField(source='village.name', read_only=True)
    
    class Meta:
        model = Business
        fields = [
            'id', 'title', 'description', 'category', 'subcategory', 'logo_url',
            'primary_image_url', 'primary_owner', 'owners_count',
            'village_name', 'contact_mobile', 'is_verified',
            'profile_score', 'views_count', 'created_at'
        ]
    
    def get_primary_owner(self, obj):
        primary = obj.owners_set.filter(role='PRIMARY', is_active=True).first()
        if primary:
            return {
                'id': primary.id,
                'name': primary.display_name,
                'contact': primary.contact_number
            }
        return None
    
    def get_owners_count(self, obj):
        return obj.owners_set.filter(is_active=True).count()
    
    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None
    
    def get_primary_image_url(self, obj):
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image and primary_image.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(primary_image.image.url)
            return primary_image.image.url
        return None
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        lang = self.context.get('lang', 'en')
        
        # Apply Gujarati translation if requested
        if lang == 'guj':
            translation = instance.translations.filter(language='guj', is_deleted=False).first()
            if translation:
                data['title'] = translation.title
                data['description'] = translation.description
        
        return data


class BusinessDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single business view"""
    category = BusinessCategorySerializer(read_only=True)
    subcategory = BusinessSubCategorySerializer(read_only=True)
    owners_set = BusinessOwnerSerializer(many=True, read_only=True)
    images = BusinessImageSerializer(many=True, read_only=True)
    translations = TranslateBusinessSerializer(many=True, read_only=True)
    
    # Location details
    village_name = serializers.CharField(source='village.name', read_only=True)
    taluka_name = serializers.CharField(source='taluka.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    
    # URLs
    logo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Business
        fields = [
            'id', 'title', 'description', 'category', 'subcategory', 'logo', 'logo_url',
            'keywords', 'village', 'village_name', 'taluka', 'taluka_name',
            'district', 'district_name', 'state', 'state_name',
            'contact_mobile', 'contact_whatsapp', 'is_verified',
            'is_active', 'profile_score', 'views_count',
            'owners_set', 'images', 'translations',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'profile_score', 'views_count', 'created_at', 'updated_at']
    
    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        lang = self.context.get('lang', 'en')
        
        # Apply Gujarati translation if requested
        if lang == 'guj':
            translation = instance.translations.filter(language='guj', is_deleted=False).first()
            if translation:
                data['title'] = translation.title
                data['description'] = translation.description
        
        return data


class BusinessCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating businesses"""
    owners = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of owners with person_id or name+mobile"
    )
    
    # Gujarati translation fields
    guj_title = serializers.CharField(write_only=True, required=False)
    guj_description = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Business
        fields = [
            'id', 'title', 'description', 'category', 'subcategory', 'logo',
            'keywords', 'village', 'taluka', 'district', 'state',
            'contact_mobile', 'contact_whatsapp',
            'owners', 'guj_title', 'guj_description'
        ]
    
    def create(self, validated_data):
        owners_data = validated_data.pop('owners', [])
        guj_title = validated_data.pop('guj_title', None)
        guj_description = validated_data.pop('guj_description', None)
        
        # Create business
        business = Business.objects.create(**validated_data)
        
        # Create Gujarati translation if provided
        if guj_title and guj_description:
            TranslateBusiness.objects.create(
                business=business,
                language='guj',
                title=guj_title,
                description=guj_description
            )
        
        # Add owners
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Add creator as primary owner
            BusinessOwner.objects.create(
                business=business,
                person=request.user.person,
                role='PRIMARY'
            )
        
        # Add additional owners
        for owner_data in owners_data:
            if 'person_id' in owner_data:
                BusinessOwner.objects.create(
                    business=business,
                    person_id=owner_data['person_id'],
                    role=owner_data.get('role', 'PARTNER')
                )
            else:
                BusinessOwner.objects.create(
                    business=business,
                    name=owner_data.get('name'),
                    mobile=owner_data.get('mobile'),
                    role=owner_data.get('role', 'PARTNER')
                )
        
        return business
    
    def update(self, instance, validated_data):
        guj_title = validated_data.pop('guj_title', None)
        guj_description = validated_data.pop('guj_description', None)
        validated_data.pop('owners', None)  # Owners updated separately
        
        # Update business
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update Gujarati translation
        if guj_title or guj_description:
            translation, created = TranslateBusiness.objects.get_or_create(
                business=instance,
                language='guj'
            )
            if guj_title:
                translation.title = guj_title
            if guj_description:
                translation.description = guj_description
            translation.save()
        
        return instance


class BusinessSearchHistorySerializer(serializers.ModelSerializer):
    """Serializer for search history"""
    person_name = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessSearchHistory
        fields = ['id', 'person', 'person_name', 'keyword', 'normalized_keyword', 'searched_at', 'last_notified_at']
        read_only_fields = ['id', 'normalized_keyword', 'searched_at']
    
    def get_person_name(self, obj):
        surname = obj.person.surname.name if obj.person.surname else ''
        return f"{obj.person.first_name} {surname}".strip()


class SearchIntentSerializer(serializers.ModelSerializer):
    """Serializer for search intent/synonyms"""
    related_terms_list = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = SearchIntent
        fields = ['id', 'keyword', 'related_terms', 'related_terms_list', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        related_terms_list = validated_data.pop('related_terms_list', None)
        if related_terms_list:
            validated_data['related_terms'] = ', '.join(related_terms_list)
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        related_terms_list = validated_data.pop('related_terms_list', None)
        if related_terms_list:
            validated_data['related_terms'] = ', '.join(related_terms_list)
        return super().update(instance, validated_data)


class SearchInterestSerializer(serializers.ModelSerializer):
    """Serializer for trending searches"""
    village_name = serializers.CharField(source='village.name', read_only=True)
    
    class Meta:
        model = SearchInterest
        fields = ['id', 'keyword', 'village', 'village_name', 'search_count', 'last_searched_at']
        read_only_fields = ['id', 'search_count', 'last_searched_at']
