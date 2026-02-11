from django.urls import path
from . import views

urlpatterns = [
    # Business Category endpoints
    path('api/v4/business-categories/', views.BusinessCategoryListView.as_view(), name='business-category-list'),
    path('api/v4/business-categories/<int:pk>/', views.BusinessCategoryDetailView.as_view(), name='business-category-detail'),
    path('api/v4/business-categories/with-counts/', views.BusinessCategoryWithCountsView.as_view(), name='business-category-with-counts'),
    
    # NEW: Subcategory endpoints
    path('api/v4/business-categories/<int:category_id>/subcategories/', views.SubCategoryListView.as_view(), name='subcategory-list'),
    path('api/v4/business-subcategories/<int:pk>/', views.SubCategoryDetailView.as_view(), name='subcategory-detail'),
    
    # Business endpoints
    path('api/v4/business/', views.BusinessListView.as_view(), name='business-list'),
    path('api/v4/business/<int:pk>/', views.BusinessDetailView.as_view(), name='business-detail'),
    path('api/v4/business/my-businesses/', views.MyBusinessesView.as_view(), name='business-my-businesses'),
    path('api/v4/business/list-by-person/<int:person_id>/', views.BusinessListByPersonView.as_view(), name='business-list-by-person'),
    path('api/v4/business/search/', views.BusinessSearchView.as_view(), name='business-search'),
    path('api/v4/business/<int:pk>/add-owner/', views.AddBusinessOwnerView.as_view(), name='business-add-owner'),
    path('api/v4/business/<int:pk>/remove-owner/<int:owner_id>/', views.RemoveBusinessOwnerView.as_view(), name='business-remove-owner'),
    path('api/v4/business/<int:pk>/upload-image/', views.UploadBusinessImageView.as_view(), name='business-upload-image'),
    
    # Search History endpoints
    path('api/v4/search-history/', views.SearchHistoryListView.as_view(), name='search-history-list'),
    path('api/v4/search-history/top-keywords/', views.TopKeywordsView.as_view(), name='search-history-top-keywords'),
    
    # Trending Searches
    path('api/v4/trending-searches/', views.TrendingSearchesView.as_view(), name='trending-searches'),
]