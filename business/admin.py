from django.contrib import admin
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


# Inline for subcategories
class BusinessSubCategoryInline(admin.TabularInline):
    model = BusinessSubCategory
    extra = 1
    fields = ('name', 'guj_name', 'icon', 'display_order', 'is_active')
    ordering = ('display_order', 'name')


@admin.register(BusinessCategory)
class BusinessCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'guj_name', 'icon', 'is_active', 'display_order', 'subcategory_count']
    list_filter = ['is_active']
    search_fields = ['name', 'guj_name']
    ordering = ['display_order', 'name']
    list_editable = ['display_order', 'is_active']
    inlines = [BusinessSubCategoryInline]
    
    def subcategory_count(self, obj):
        return obj.subcategories.count()
    subcategory_count.short_description = 'Subcategories'


@admin.register(BusinessSubCategory)
class BusinessSubCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'category', 'guj_name', 'icon', 'display_order', 'is_active', 'business_count']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'guj_name', 'category__name']
    ordering = ['category', 'display_order', 'name']
    list_editable = ['display_order', 'is_active']
    
    def business_count(self, obj):
        return obj.businesses.filter(is_active=True, is_deleted=False).count()
    business_count.short_description = 'Businesses'


class BusinessOwnerInline(admin.TabularInline):
    model = BusinessOwner
    extra = 1
    readonly_fields = ['owner_type', 'display_name', 'contact_number', 'added_at']
    fields = ['person', 'name', 'mobile', 'role', 'owner_type', 'is_active', 'display_name', 'contact_number', 'added_at']
    
    def display_name(self, obj):
        return obj.display_name if obj.id else '-'
    display_name.short_description = 'Display Name'
    
    def contact_number(self, obj):
        return obj.contact_number if obj.id else '-'
    contact_number.short_description = 'Contact'


class BusinessImageInline(admin.TabularInline):
    model = BusinessImage
    extra = 1
    readonly_fields = ['thumbnail_preview', 'uploaded_at']
    fields = ['image', 'thumbnail_preview', 'is_primary', 'display_order', 'uploaded_at']
    
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return f'<img src="{obj.thumbnail.url}" width="100" height="100" />'
        return '-'
    thumbnail_preview.short_description = 'Thumbnail'
    thumbnail_preview.allow_tags = True


class TranslateBusinessInline(admin.StackedInline):
    model = TranslateBusiness
    extra = 1
    fields = ['language', 'title', 'description', 'is_deleted']


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'title',
        'category',
        'subcategory',
        'village',
        'primary_owner_name',
        'is_verified',
        'is_active',
        'profile_score',
        'views_count',
        'created_at'
    ]
    list_filter = [
        'category',
        'subcategory',
        'is_verified',
        'is_active',
        'is_deleted',
        'village__taluka',
        'created_at'
    ]
    search_fields = ['title', 'keywords', 'contact_mobile', 'contact_whatsapp']
    readonly_fields = ['profile_score', 'views_count', 'created_at', 'updated_at', 'deleted_at']
    inlines = [BusinessOwnerInline, BusinessImageInline, TranslateBusinessInline]
    actions = ['verify_businesses', 'unverify_businesses', 'activate_businesses', 'deactivate_businesses']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'category', 'subcategory', 'logo', 'keywords')
        }),
        ('Location', {
            'fields': ('village', 'taluka', 'district', 'state')
        }),
        ('Contact', {
            'fields': ('contact_mobile', 'contact_whatsapp')
        }),
        ('Status', {
            'fields': ('is_verified', 'is_active', 'is_deleted')
        }),
        ('Analytics', {
            'fields': ('profile_score', 'views_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
    
    def primary_owner_name(self, obj):
        primary = obj.owners_set.filter(role='PRIMARY').first()
        if primary:
            return primary.display_name
        return '-'
    primary_owner_name.short_description = 'Primary Owner'
    
    def verify_businesses(self, request, queryset):
        count = queryset.update(is_verified=True)
        self.message_user(request, f"{count} business(es) verified successfully.")
    verify_businesses.short_description = "Verify selected businesses"
    
    def unverify_businesses(self, request, queryset):
        count = queryset.update(is_verified=False)
        self.message_user(request, f"{count} business(es) unverified.")
    unverify_businesses.short_description = "Unverify selected businesses"
    
    def activate_businesses(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} business(es) activated.")
    activate_businesses.short_description = "Activate selected businesses"
    
    def deactivate_businesses(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} business(es) deactivated.")
    deactivate_businesses.short_description = "Deactivate selected businesses"


@admin.register(BusinessOwner)
class BusinessOwnerAdmin(admin.ModelAdmin):
    list_display = ['id', 'business', 'display_name', 'contact_number', 'role', 'owner_type', 'is_active', 'added_at']
    list_filter = ['role', 'owner_type', 'is_active']
    search_fields = ['business__title', 'name', 'mobile', 'person__first_name']
    readonly_fields = ['owner_type', 'display_name', 'contact_number', 'added_at']
    
    fieldsets = (
        ('Business', {
            'fields': ('business',)
        }),
        ('Owner Information', {
            'fields': ('person', 'name', 'mobile', 'owner_type')
        }),
        ('Role & Status', {
            'fields': ('role', 'is_active')
        }),
        ('Computed Fields', {
            'fields': ('display_name', 'contact_number', 'added_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TranslateBusiness)
class TranslateBusinessAdmin(admin.ModelAdmin):
    list_display = ['id', 'business', 'language', 'title', 'is_deleted']
    list_filter = ['language', 'is_deleted']
    search_fields = ['business__title', 'title', 'description']


@admin.register(BusinessImage)
class BusinessImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'business', 'image_preview', 'is_primary', 'display_order', 'uploaded_at']
    list_filter = ['is_primary', 'uploaded_at']
    search_fields = ['business__title']
    readonly_fields = ['image_preview', 'thumbnail_preview', 'uploaded_at']
    list_editable = ['is_primary', 'display_order']
    
    def image_preview(self, obj):
        if obj.image:
            return f'<img src="{obj.image.url}" width="100" height="100" />'
        return '-'
    image_preview.short_description = 'Image'
    image_preview.allow_tags = True
    
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return f'<img src="{obj.thumbnail.url}" width="100" height="100" />'
        return '-'
    thumbnail_preview.short_description = 'Thumbnail'
    thumbnail_preview.allow_tags = True


@admin.register(BusinessSearchHistory)
class BusinessSearchHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'person_name', 'keyword', 'normalized_keyword', 'searched_at', 'last_notified_at']
    list_filter = ['searched_at', 'last_notified_at']
    search_fields = ['person__first_name', 'keyword', 'normalized_keyword']
    readonly_fields = ['searched_at']
    date_hierarchy = 'searched_at'
    
    def person_name(self, obj):
        return f"{obj.person.first_name} {obj.person.surname.name if obj.person.surname else ''}"
    person_name.short_description = 'Person'


@admin.register(SearchIntent)
class SearchIntentAdmin(admin.ModelAdmin):
    list_display = ['id', 'keyword', 'related_terms_preview', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['keyword', 'related_terms']
    list_editable = ['is_active']
    
    def related_terms_preview(self, obj):
        terms = obj.related_terms
        if len(terms) > 50:
            return terms[:50] + '...'
        return terms
    related_terms_preview.short_description = 'Related Terms'


@admin.register(SearchInterest)
class SearchInterestAdmin(admin.ModelAdmin):
    list_display = ['id', 'keyword', 'village', 'search_count', 'last_searched_at']
    list_filter = ['village', 'last_searched_at']
    search_fields = ['keyword', 'village__name']
    readonly_fields = ['last_searched_at']
    ordering = ['-search_count', '-last_searched_at']
