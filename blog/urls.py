from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # Main views
    path('', views.PostListView.as_view(), name='post_list'),
    path('post/<slug:slug>/', views.PostDetailView.as_view(), name='post_detail'),
    
    # Category and filtering
    path('category/<slug:slug>/', views.CategoryPostListView.as_view(), name='category_detail'),
    path('tag/<slug:tag>/', views.TagPostListView.as_view(), name='tag_detail'),
    path('author/<str:username>/', views.AuthorPostListView.as_view(), name='author_detail'),
    
    # Search
    path('search/', views.SearchView.as_view(), name='search'),
    
    # User features
    path('saved/', views.saved_posts_view, name='saved_posts'),
    path('post/create/', views.CreatePostView.as_view(), name='post_create'),
    path('post/<slug:slug>/edit/', views.UpdatePostView.as_view(), name='post_edit'),
    
    # AJAX endpoints
    path('api/post/<int:post_id>/save/', views.save_post, name='save_post'),
]