from rest_framework import serializers
from .models import (
    DemoPerson, DemoSurname, DemoBusiness, 
    DemoBusinessCategory, DemoNotification, DemoBusinessSubCategory,
    DemoState, DemoDistrict, DemoTaluka, DemoVillage, DemoParentChildRelation,
    DemoCountry
)

class DemoCountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoCountry
        fields = ['id', 'name', 'guj_name']
    def to_representation(self, instance):
        lang = self.context.get('lang', 'en')
        data = super().to_representation(instance)
        if lang == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        return data

class DemoStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoState
        fields = ['id', 'name', 'guj_name']
    def to_representation(self, instance):
        lang = self.context.get('lang', 'en')
        data = super().to_representation(instance)
        if lang == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        return data

class DemoDistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoDistrict
        fields = ['id', 'state', 'name', 'guj_name']
    def to_representation(self, instance):
        lang = self.context.get('lang', 'en')
        data = super().to_representation(instance)
        if lang == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        return data

class DemoTalukaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoTaluka
        fields = ['id', 'district', 'name', 'guj_name']
    def to_representation(self, instance):
        lang = self.context.get('lang', 'en')
        data = super().to_representation(instance)
        if lang == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        return data

class DemoVillageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoVillage
        fields = ['id', 'taluka', 'name', 'guj_name']
    def to_representation(self, instance):
        lang = self.context.get('lang', 'en')
        data = super().to_representation(instance)
        if lang == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        return data

class DemoSurnameSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoSurname
        fields = ['id', 'name', 'guj_name']

    def to_representation(self, instance):
        lang = self.context.get('lang', 'en')
        data = super().to_representation(instance)
        if lang == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        return data

class DemoPersonSerializer(serializers.ModelSerializer):
    surname_name = serializers.ReadOnlyField(source='surname.name')
    village_name = serializers.ReadOnlyField(source='village.name')
    state_name = serializers.ReadOnlyField(source='state.name')
    district_name = serializers.ReadOnlyField(source='district.name')
    taluka_name = serializers.ReadOnlyField(source='taluka.name')

    class Meta:
        model = DemoPerson
        fields = [
            'id', 'first_name', 'middle_name', 'surname', 'surname_name',
            'mobile_number1', 'mobile_number2', 'state', 'state_name', 'district', 'district_name',
            'taluka', 'taluka_name', 'village', 'village_name', 'profile_pic',
            'is_admin', 'flag_show', 'is_super_admin', 'is_registered_directly',
            'guj_first_name', 'guj_middle_name', 'date_of_birth', 'address',
            'is_out_of_country', 'out_of_country', 'country_mobile_number'
        ]

    def to_representation(self, instance):
        lang = self.context.get('lang', 'en')
        data = super().to_representation(instance)
        if lang == 'guj':
            data['first_name'] = instance.guj_first_name or instance.first_name
            data['middle_name'] = instance.guj_middle_name or instance.middle_name
            if instance.surname and instance.surname.guj_name:
                data['surname_name'] = instance.surname.guj_name
            if instance.village and instance.village.guj_name:
                data['village_name'] = instance.village.guj_name
            if instance.state and instance.state.guj_name:
                data['state_name'] = instance.state.guj_name
            if instance.district and instance.district.guj_name:
                data['district_name'] = instance.district.guj_name
            if instance.taluka and instance.taluka.guj_name:
                data['taluka_name'] = instance.taluka.guj_name
        return data

class DemoBusinessCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoBusinessCategory
        fields = ['id', 'name', 'guj_name', 'icon']

    def to_representation(self, instance):
        lang = self.context.get('lang', 'en')
        data = super().to_representation(instance)
        if lang == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        return data

class DemoBusinessSubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoBusinessSubCategory
        fields = ['id', 'category', 'name', 'guj_name']

    def to_representation(self, instance):
        lang = self.context.get('lang', 'en')
        data = super().to_representation(instance)
        if lang == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        return data

class DemoBusinessSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    subcategory_name = serializers.ReadOnlyField(source='subcategory.name')
    village_name = serializers.ReadOnlyField(source='village.name')

    class Meta:
        model = DemoBusiness
        fields = [
            'id', 'title', 'guj_title', 'description', 'category', 'category_name',
            'subcategory', 'subcategory_name',
            'village', 'village_name', 'contact_mobile'
        ]

    def to_representation(self, instance):
        lang = self.context.get('lang', 'en')
        data = super().to_representation(instance)
        if lang == 'guj':
            data['title'] = instance.guj_title or instance.title
            if instance.category and instance.category.guj_name:
                data['category_name'] = instance.category.guj_name
            if instance.subcategory and instance.subcategory.guj_name:
                data['subcategory_name'] = instance.subcategory.guj_name
            if instance.village and instance.village.guj_name:
                data['village_name'] = instance.village.guj_name
        return data

class DemoNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoNotification
        fields = ['id', 'title', 'subtitle', 'is_event', 'created_at']

class DemoProfileSerializer(DemoPersonSerializer):
    parents = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    businesses = serializers.SerializerMethodField()

    class Meta(DemoPersonSerializer.Meta):
        fields = DemoPersonSerializer.Meta.fields + ['parents', 'children', 'businesses']

    def get_parents(self, obj):
        lang = self.context.get('lang', 'en')
        # Find people who are parents of this person
        parent_ids = DemoParentChildRelation.objects.filter(child=obj).values_list('parent_id', flat=True)
        parents = DemoPerson.objects.filter(id__in=parent_ids)
        return DemoPersonSerializer(parents, many=True, context={'lang': lang}).data

    def get_children(self, obj):
        lang = self.context.get('lang', 'en')
        # Find people who are children of this person
        child_ids = DemoParentChildRelation.objects.filter(parent=obj).values_list('child_id', flat=True)
        children = DemoPerson.objects.filter(id__in=child_ids)
        return DemoPersonSerializer(children, many=True, context={'lang': lang}).data

    def get_businesses(self, obj):
        lang = self.context.get('lang', 'en')
        # Use the related name from DemoBusiness.owners
        businesses = obj.demo_businesses.all()
        return DemoBusinessSerializer(businesses, many=True, context={'lang': lang}).data

class DemoPersonRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoPerson
        fields = [
            'first_name', 'middle_name', 'surname', 'mobile_number1', 'mobile_number2',
            'state', 'district', 'taluka', 'village', 'date_of_birth', 'address',
            'guj_first_name', 'guj_middle_name', 'platform',
            'is_out_of_country', 'out_of_country', 'country_mobile_number'
        ]
