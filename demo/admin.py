from django.contrib import admin
from .models import (
    DemoState, DemoDistrict, DemoTaluka, DemoVillage,
    DemoSurname, DemoPerson,    DemoParentChildRelation, DemoBusinessCategory, DemoBusinessSubCategory,
    DemoBusiness, DemoNotification, DemoCountry
)

@admin.register(DemoState)
class DemoStateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'guj_name')
    search_fields = ('name', 'guj_name')

@admin.register(DemoDistrict)
class DemoDistrictAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'guj_name', 'state')
    list_filter = ('state',)
    search_fields = ('name', 'guj_name')

@admin.register(DemoTaluka)
class DemoTalukaAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'guj_name', 'district')
    list_filter = ('district__state', 'district')
    search_fields = ('name', 'guj_name')

@admin.register(DemoVillage)
class DemoVillageAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'guj_name', 'taluka')
    list_filter = ('taluka__district__state', 'taluka__district', 'taluka')
    search_fields = ('name', 'guj_name')

@admin.register(DemoSurname)
class DemoSurnameAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'guj_name', 'top_member')
    search_fields = ('name', 'guj_name')

@admin.register(DemoPerson)
class DemoPersonAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'surname', 'mobile_number1', 'village', 'is_admin', 'flag_show', 'is_out_of_country')
    list_filter = ('surname', 'village', 'is_admin', 'flag_show', 'is_out_of_country')
    search_fields = ('first_name', 'mobile_number1', 'surname__name')
    autocomplete_fields = ('surname', 'village', 'state', 'district', 'taluka')

@admin.register(DemoParentChildRelation)
class DemoParentChildRelationAdmin(admin.ModelAdmin):
    list_display = ('id', 'parent', 'child')
    autocomplete_fields = ('parent', 'child')

@admin.register(DemoBusinessCategory)
class DemoBusinessCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'guj_name', 'icon')
    search_fields = ('name', 'guj_name')
@admin.register(DemoCountry)
class DemoCountryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'guj_name')
    search_fields = ('name', 'guj_name')

@admin.register(DemoBusinessSubCategory)
class DemoBusinessSubCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'guj_name', 'category')
    list_filter = ('category',)
    search_fields = ('name', 'guj_name')

@admin.register(DemoBusiness)
class DemoBusinessAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'category', 'subcategory', 'village')
    list_filter = ('category', 'subcategory', 'village')
    search_fields = ('title', 'guj_title', 'description')
    autocomplete_fields = ('category', 'subcategory', 'village', 'owners')

@admin.register(DemoNotification)
class DemoNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'is_event', 'created_at')
    list_filter = ('is_event', 'village_target', 'surname_target')
    search_fields = ('title', 'subtitle')
