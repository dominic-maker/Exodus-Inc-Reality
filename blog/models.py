"""
Blog Models - Enhanced with SEO, Analytics, and Advanced Features
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import F
from taggit.managers import TaggableManager  # Add this import

User = get_user_model()


class Category(models.Model):
    """Enhanced category model with hierarchical support and SEO"""
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, help_text="Category description for SEO")
    
    # Hierarchical categories (parent/child)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="Parent category for nested categories"
    )
    
    # Media
    image = models.ImageField(
        upload_to='blog/categories/', 
        blank=True, 
        null=True,
        help_text="Category featured image"
    )
    
    # SEO fields
    meta_description = models.CharField(
        max_length=160, 
        blank=True,
        help_text="SEO meta description"
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text="Display order (lower numbers first)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'order']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        """Display full category path"""
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided"""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:category_detail", kwargs={"slug": self.slug})

    def get_post_count(self):
        """Get count of published posts in this category"""
        return self.posts.filter(status='published').count()

    def get_all_children(self):
        """Get all child categories recursively"""
        children = []
        for child in self.children.all():
            children.append(child)
            children.extend(child.get_all_children())
        return children

class Post(models.Model):
    """Enhanced post model"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    # Core fields
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='blog_posts'
    )
    title = models.CharField(max_length=220, db_index=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    subtitle = models.CharField(
        max_length=250, 
        blank=True,
        help_text="Optional subtitle for the post"
    )
    
    # Content
    excerpt = models.TextField(
        max_length=500, 
        blank=True,
        help_text="Short description (auto-generated if empty)"
    )
    content = models.TextField(help_text="Main post content")
    
    # Media
    featured_image = models.ImageField(
        upload_to='blog/posts/%Y/%m/',
        blank=True,
        null=True,
        help_text="Featured image for the post"
    )
    featured_image_alt = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Alt text for featured image (SEO)"
    )
    video_url = models.URLField(
        blank=True,
        help_text="YouTube or Vimeo URL (optional)"
    )
    
    # Taxonomy
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts'
    )
    
    # TAGS - Add this line
    tags = TaggableManager(blank=True, help_text="Tags for this post")
    
    # Status & Publishing
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True
    )
    published_at = models.DateTimeField(
        null=True, 
        blank=True, 
        db_index=True,
        help_text="Publication date and time"
    )
    featured = models.BooleanField(
        default=False, 
        db_index=True,
        help_text="Feature this post on homepage"
    )
    allow_comments = models.BooleanField(
        default=True,
        help_text="Allow users to comment on this post"
    )
    
    # SEO fields
    meta_title = models.CharField(
        max_length=70, 
        blank=True,
        help_text="SEO title (defaults to post title)"
    )
    meta_description = models.CharField(
        max_length=160, 
        blank=True,
        help_text="SEO meta description"
    )
    meta_keywords = models.CharField(
        max_length=255, 
        blank=True,
        help_text="SEO keywords (comma-separated)"
    )
    
    # Social Media (Open Graph)
    og_title = models.CharField(
        max_length=95, 
        blank=True,
        help_text="Open Graph title for social sharing"
    )
    og_description = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Open Graph description"
    )
    og_image = models.ImageField(
        upload_to='blog/og_images/', 
        blank=True, 
        null=True,
        help_text="Open Graph image (1200x630 recommended)"
    )
    
    # Analytics
    views = models.PositiveIntegerField(
        default=0, 
        db_index=True,
        help_text="Number of views"
    )
    reading_time = models.PositiveIntegerField(
        default=0,
        help_text='Estimated reading time in minutes'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['author', '-published_at']),
            models.Index(fields=['category', '-published_at']),
            models.Index(fields=['-views']),
            models.Index(fields=['featured', '-published_at']),
        ]
        verbose_name = 'Blog Post'
        verbose_name_plural = 'Blog Posts'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Auto-generate slug, excerpt, and reading time"""
        # Auto-generate slug from title
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Post.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Set published_at when status changes to published
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        
        # Auto-generate excerpt if empty
        if not self.excerpt and self.content:
            import re
            text = re.sub(r'<[^>]+>', '', self.content)
            self.excerpt = text[:200] + '...' if len(text) > 200 else text
        
        # Calculate reading time
        if self.content:
            word_count = len(self.content.split())
            self.reading_time = max(1, round(word_count / 200))
        
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:post_detail", kwargs={"slug": self.slug})

    def increment_views(self):
        """Increment post view count atomically"""
        Post.objects.filter(pk=self.pk).update(views=F('views') + 1)
        self.refresh_from_db()

    def get_related_posts(self, limit=4):
        """Get related posts based on tags and category"""
        return Post.objects.filter(
            status='published'
        ).filter(
            models.Q(tags__in=self.tags.all()) | models.Q(category=self.category)
        ).exclude(
            id=self.id
        ).distinct()[:limit]

class Comment(models.Model):
    """Comment system with moderation and threading"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('spam', 'Spam'),
        ('trash', 'Trash'),
    ]
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        help_text="Parent comment for threaded replies"
    )
    
    # User info (for both authenticated and guest users)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='blog_comments'
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    website = models.URLField(blank=True)
    
    # Content
    content = models.TextField()
    
    # Moderation
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'status', 'created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['parent']),
        ]
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'

    def __str__(self):
        return f'Comment by {self.name} on {self.post.title}'

    def get_replies(self):
        """Get approved replies to this comment"""
        return self.replies.filter(status='approved').order_by('created_at')


class PostView(models.Model):
    """Track individual post views for analytics"""
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='post_views'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255, blank=True)
    referer = models.URLField(blank=True, max_length=500)
    session_key = models.CharField(max_length=40, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['post', '-viewed_at']),
            models.Index(fields=['ip_address', 'session_key']),
        ]
        verbose_name = 'Post View'
        verbose_name_plural = 'Post Views'

    def __str__(self):
        return f'View of {self.post.title} at {self.viewed_at}'


class SavedPost(models.Model):
    """User saved/bookmarked posts"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='saved_posts'
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='saved_by'
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'post']
        ordering = ['-saved_at']
        indexes = [
            models.Index(fields=['user', '-saved_at']),
        ]
        verbose_name = 'Saved Post'
        verbose_name_plural = 'Saved Posts'

    def __str__(self):
        return f'{self.user.username} saved {self.post.title}'


class Newsletter(models.Model):
    """Newsletter subscription model"""
    
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    confirmed = models.BooleanField(default=False)
    confirmation_token = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    subscribed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-subscribed_at']
        indexes = [
            models.Index(fields=['email', 'is_active']),
        ]
        verbose_name = 'Newsletter Subscription'
        verbose_name_plural = 'Newsletter Subscriptions'

    def __str__(self):
        status = 'Active' if self.is_active else 'Inactive'
        return f'{self.email} ({status})'


# Optional: Tag model if not using django-taggit
class Tag(models.Model):
    """Simple tag model (use this if not using django-taggit)"""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# Add ManyToMany field to Post if using simple Tag model
# Add this to Post model:
# tags = models.ManyToManyField(Tag, blank=True, related_name='posts')
