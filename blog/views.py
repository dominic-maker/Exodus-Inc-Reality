
from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.views.generic.edit import FormMixin
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.db.models import Q, Count, Prefetch
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.urls import reverse_lazy

from .models import Post, Category, Comment, SavedPost, PostView
from .forms import CommentForm, SearchForm


class PostListView(ListView):
    model = Post
    template_name = "blog/post_list.html"
    context_object_name = 'posts'
    paginate_by = 6

    def get_queryset(self):
        """Optimized queryset with related data and filtering"""
        queryset = Post.objects.filter(
            status='published',
            published_at__lte=timezone.now()
        ).select_related(
            'author',
            'category'
        ).prefetch_related(
            'tags'
        ).annotate(
            comment_count=Count('comments', filter=Q(comments__status='approved'))
        ).order_by('-published_at')

        # Search functionality
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(content__icontains=search_query) |
                Q(excerpt__icontains=search_query) |
                Q(tags__name__icontains=search_query)
            ).distinct()

        # Tag filtering
        tag = self.request.GET.get('tag')
        if tag:
            queryset = queryset.filter(tags__slug=tag)

        # Featured posts filter
        if self.request.GET.get('featured'):
            queryset = queryset.filter(featured=True)

        return queryset

    def get_context_data(self, **kwargs):
        """Add extra context data"""
        context = super().get_context_data(**kwargs)
        
        # Featured posts for sidebar/hero
        context['featured_posts'] = cache.get_or_set(
            'featured_posts',
            lambda: Post.objects.filter(
                status='published',
                featured=True,
                published_at__lte=timezone.now()
            ).select_related('author', 'category')[:5],
            60 * 15  # Cache for 15 minutes
        )
        
        # Categories with post count
        context['categories'] = cache.get_or_set(
            'categories_with_count',
            lambda: Category.objects.filter(
                is_active=True
            ).annotate(
                post_count=Count('posts', filter=Q(posts__status='published'))
            ).filter(post_count__gt=0),
            60 * 30  # Cache for 30 minutes
        )
        
        # Popular posts (by views)
        context['popular_posts'] = cache.get_or_set(
            'popular_posts',
            lambda: Post.objects.filter(
                status='published',
                published_at__lte=timezone.now()
            ).order_by('-views')[:5],
            60 * 15  # Cache for 15 minutes
        )
        
        # Recent posts
        context['recent_posts'] = Post.objects.filter(
            status='published',
            published_at__lte=timezone.now()
        ).order_by('-published_at')[:5]
        
        # Search form
        context['search_form'] = SearchForm(self.request.GET)
        
        # Search query for template
        context['search_query'] = self.request.GET.get('q', '')
        
        return context


class PostDetailView(FormMixin, DetailView):
    """Enhanced post detail with comments, analytics, and related posts"""
    model = Post
    template_name = "blog/post_detail.html"
    context_object_name = 'post'
    form_class = CommentForm

    def get_queryset(self):
        """Optimized queryset with prefetched relations"""
        queryset = Post.objects.filter(
            status='published'
        ).select_related(
            'author',
            'category'
        ).prefetch_related(
            'tags',
            Prefetch(
                'comments',
                queryset=Comment.objects.filter(
                    status='approved',
                    parent__isnull=True
                ).select_related('user').prefetch_related('replies')
            )
        )
        return queryset

    def get_object(self):
        """Get post and track view"""
        obj = super().get_object()
        
        # Track view with session-based deduplication
        self._track_view(obj)
        
        return obj

    def _track_view(self, post):
        """Track post view with session deduplication"""
        session_key = self.request.session.session_key
        if not session_key:
            self.request.session.create()
            session_key = self.request.session.session_key

        # Check if already viewed in this session
        view_key = f'post_view_{post.id}_{session_key}'
        if not cache.get(view_key):
            # Create view record
            PostView.objects.create(
                post=post,
                user=self.request.user if self.request.user.is_authenticated else None,
                ip_address=self._get_client_ip(),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:255],
                referer=self.request.META.get('HTTP_REFERER', '')[:500],
                session_key=session_key
            )
            
            # Increment view count
            Post.objects.filter(id=post.id).update(views=models.F('views') + 1)
            
            # Cache for 30 minutes to prevent duplicate counting
            cache.set(view_key, True, 60 * 30)

    def _get_client_ip(self):
        """Extract client IP address from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '')
        return ip

    def get_context_data(self, **kwargs):
        """Add related posts, comments, and other context"""
        context = super().get_context_data(**kwargs)
        post = self.object
        
        # Related posts based on tags and category
        related_posts = Post.objects.filter(
            status='published'
        ).filter(
            Q(tags__in=post.tags.all()) | Q(category=post.category)
        ).exclude(
            id=post.id
        ).annotate(
            same_tags=Count('tags', filter=Q(tags__in=post.tags.all()))
        ).order_by('-same_tags', '-published_at').distinct()[:4]
        
        context['related_posts'] = related_posts
        
        # Previous and next posts
        context['previous_post'] = Post.objects.filter(
            status='published',
            published_at__lt=post.published_at
        ).order_by('-published_at').first()
        
        context['next_post'] = Post.objects.filter(
            status='published',
            published_at__gt=post.published_at
        ).order_by('published_at').first()
        
        # Check if user saved this post
        if self.request.user.is_authenticated:
            context['is_saved'] = SavedPost.objects.filter(
                user=self.request.user,
                post=post
            ).exists()
        
        # Comments
        context['comments'] = post.comments.filter(
            status='approved',
            parent__isnull=True
        ).select_related('user').prefetch_related('replies')
        
        context['comment_count'] = post.comments.filter(status='approved').count()
        
        # Social sharing URLs
        context['share_url'] = self.request.build_absolute_uri()
        
        return context

    def post(self, request, *args, **kwargs):
        """Handle comment form submission"""
        self.object = self.get_object()
        form = self.get_form()
        
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Save comment with proper status"""
        comment = form.save(commit=False)
        comment.post = self.object
        
        if self.request.user.is_authenticated:
            comment.user = self.request.user
            comment.name = self.request.user.get_full_name() or self.request.user.username
            comment.email = self.request.user.email
            # Auto-approve for authenticated users
            comment.status = 'approved'
        else:
            # Pending moderation for guests
            comment.status = 'pending'
        
        # Capture IP and user agent
        comment.ip_address = self._get_client_ip()
        comment.user_agent = self.request.META.get('HTTP_USER_AGENT', '')[:255]
        
        comment.save()
        
        if comment.status == 'approved':
            messages.success(self.request, 'Comment posted successfully!')
        else:
            messages.info(self.request, 'Your comment is awaiting moderation.')
        
        return redirect(self.object.get_absolute_url() + '#comments')

    def form_invalid(self, form):
        """Handle invalid form"""
        messages.error(self.request, 'Please correct the errors in your comment.')
        return self.render_to_response(self.get_context_data(form=form))


class CategoryPostListView(ListView):
    """Enhanced category view with breadcrumbs and subcategories"""
    model = Post
    template_name = "blog/post_category.html"
    context_object_name = 'posts'
    paginate_by = 6

    def get_queryset(self):
        """Get posts for specific category"""
        self.category = get_object_or_404(Category, slug=self.kwargs["slug"])
        return Post.objects.filter(
            category=self.category,
            status='published',
            published_at__lte=timezone.now()
        ).select_related(
            'author',
            'category'
        ).prefetch_related(
            'tags'
        ).annotate(
            comment_count=Count('comments', filter=Q(comments__status='approved'))
        ).order_by('-published_at')

    def get_context_data(self, **kwargs):
        """Add category and related context"""
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        
        # Subcategories if any
        context['subcategories'] = Category.objects.filter(
            parent=self.category,
            is_active=True
        ).annotate(
            post_count=Count('posts', filter=Q(posts__status='published'))
        )
        
        # Breadcrumb trail for nested categories
        breadcrumbs = []
        current = self.category
        while current:
            breadcrumbs.insert(0, current)
            current = current.parent
        context['breadcrumbs'] = breadcrumbs
        
        return context


class TagPostListView(ListView):
    """View posts by tag"""
    model = Post
    template_name = "blog/post_tag.html"
    context_object_name = 'posts'
    paginate_by = 6

    def get_queryset(self):
        """Get posts with specific tag"""
        self.tag = self.kwargs['tag']
        return Post.objects.filter(
            tags__slug=self.tag,
            status='published',
            published_at__lte=timezone.now()
        ).select_related(
            'author',
            'category'
        ).prefetch_related('tags').order_by('-published_at')

    def get_context_data(self, **kwargs):
        """Add tag context"""
        context = super().get_context_data(**kwargs)
        context['tag'] = self.tag
        return context


class AuthorPostListView(ListView):
    """View posts by author"""
    model = Post
    template_name = "blog/post_author.html"
    context_object_name = 'posts'
    paginate_by = 6

    def get_queryset(self):
        """Get posts by specific author"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.author = get_object_or_404(User, username=self.kwargs['username'])
        
        return Post.objects.filter(
            author=self.author,
            status='published',
            published_at__lte=timezone.now()
        ).select_related(
            'author',
            'category'
        ).prefetch_related('tags').order_by('-published_at')

    def get_context_data(self, **kwargs):
        """Add author context"""
        context = super().get_context_data(**kwargs)
        context['author'] = self.author
        context['post_count'] = self.get_queryset().count()
        return context


class SearchView(ListView):
    """Enhanced search with multiple filters"""
    model = Post
    template_name = "blog/search_results.html"
    context_object_name = 'posts'
    paginate_by = 6

    def get_queryset(self):
        """Search across multiple fields"""
        query = self.request.GET.get('q', '')
        
        if not query:
            return Post.objects.none()
        
        # Full-text search
        queryset = Post.objects.filter(
            status='published',
            published_at__lte=timezone.now()
        ).filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(excerpt__icontains=query) |
            Q(tags__name__icontains=query) |
            Q(category__name__icontains=query)
        ).select_related(
            'author',
            'category'
        ).prefetch_related('tags').distinct().order_by('-published_at')
        
        return queryset

    def get_context_data(self, **kwargs):
        """Add search context"""
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['result_count'] = self.get_queryset().count()
        return context


# ============================================================================
# AJAX VIEWS
# ============================================================================

@login_required
@require_POST
def save_post(request, post_id):
    """Save/unsave a post (bookmark)"""
    post = get_object_or_404(Post, id=post_id, status='published')
    
    saved_post, created = SavedPost.objects.get_or_create(
        user=request.user,
        post=post
    )
    
    if not created:
        saved_post.delete()
        return JsonResponse({
            'success': True,
            'saved': False,
            'message': 'Post removed from saved items'
        })
    
    return JsonResponse({
        'success': True,
        'saved': True,
        'message': 'Post saved successfully'
    })


@login_required
def saved_posts_view(request):
    """View user's saved/bookmarked posts"""
    saved_posts = SavedPost.objects.filter(
        user=request.user
    ).select_related(
        'post__author',
        'post__category'
    ).prefetch_related(
        'post__tags'
    ).order_by('-saved_at')
    
    paginator = Paginator(saved_posts, 12)
    page = request.GET.get('page')
    
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    
    return render(request, 'blog/saved_posts.html', {
        'saved_posts': posts
    })


# ============================================================================
# CONTENT CREATION VIEWS (For Authenticated Users)
# ============================================================================

class CreatePostView(LoginRequiredMixin, CreateView):
    """Allow authenticated users to create blog posts"""
    model = Post
    template_name = 'blog/post_form.html'
    fields = ['title', 'subtitle', 'category', 'tags', 'excerpt', 
              'content', 'featured_image', 'featured_image_alt', 'allow_comments']
    login_url = '/accounts/login/'
    
    def form_valid(self, form):
        """Set author and default status"""
        form.instance.author = self.request.user
        # New posts start as draft for non-staff users
        if not self.request.user.is_staff:
            form.instance.status = 'draft'
            messages.success(self.request, 'Post created as draft. It will be reviewed before publishing.')
        else:
            form.instance.status = 'published'
            form.instance.published_at = timezone.now()
            messages.success(self.request, 'Post published successfully!')
        
        return super().form_valid(form)
    
    def get_success_url(self):
        """Redirect based on post status"""
        if self.object.status == 'published':
            return self.object.get_absolute_url()
        else:
            return reverse_lazy('dashboard')  # Or your user dashboard


class UpdatePostView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Allow users to edit their own posts"""
    model = Post
    template_name = 'blog/post_form.html'
    fields = ['title', 'subtitle', 'category', 'tags', 'excerpt', 
              'content', 'featured_image', 'featured_image_alt', 'allow_comments']
    
    def test_func(self):
        """Check if user is the author or staff"""
        post = self.get_object()
        return self.request.user == post.author or self.request.user.is_staff
    
    def form_valid(self, form):
        """Update post"""
        messages.success(self.request, 'Post updated successfully!')
        return super().form_valid(form)
