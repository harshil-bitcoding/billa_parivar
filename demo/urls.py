from django.urls import path
from .views import (
    DemoLoginAPI, DemoPersonViewSet, DemoBusinessViewSet, 
    DemoNotificationListView, DemoVillageListView, DemoRelationtreeAPIView,
    DemoBusinessSubCategoryViewSet, DemoBusinessCategoryViewSet,
    DemoStateListView, DemoDistrictListView, DemoTalukaListView, DemoProfileAPIView,
    DemoRegisterAPIView, DemoCSVUploadAPIView
)

urlpatterns = [
    # Auth & General
    path('login/', DemoLoginAPI.as_view(), name='demo-login'),
    path('register/', DemoRegisterAPIView.as_view(), name='demo-register'),
    path('upload-csv/', DemoCSVUploadAPIView.as_view(), name='demo-upload-csv'),
    path('notifications/', DemoNotificationListView.as_view(), name='demo-notifications'),
    
    # Hierarchical Locations
    path('states/', DemoStateListView.as_view(), name='demo-state-list'),
    path('districts/', DemoDistrictListView.as_view(), name='demo-district-list'),
    path('talukas/', DemoTalukaListView.as_view(), name='demo-taluka-list'),
    path('villages/', DemoVillageListView.as_view(), name='demo-village-list'),
    
    # Family Tree
    path('relation-tree/', DemoRelationtreeAPIView.as_view(), name='demo-relation-tree'),
    path('profile/', DemoProfileAPIView.as_view(), name='demo-profile'),
    
    # Person Profiles
    path('person/', DemoPersonViewSet.as_view({'get': 'list'}), name='demo-person-list'),
    path('person/<int:pk>/', DemoPersonViewSet.as_view({'get': 'retrieve'}), name='demo-person-detail'),
    
    # Business Directory
    path('business-category/', DemoBusinessCategoryViewSet.as_view({'get': 'list'}), name='demo-business-category-list'),
    path('business-subcategory/', DemoBusinessSubCategoryViewSet.as_view({'get': 'list'}), name='demo-business-subcategory-list'),
    path('business/', DemoBusinessViewSet.as_view({'get': 'list'}), name='demo-business-list'),
    path('business/<int:pk>/', DemoBusinessViewSet.as_view({'get': 'retrieve'}), name='demo-business-detail'),
]
