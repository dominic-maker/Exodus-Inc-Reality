from django import forms
from django.core.exceptions import ValidationError
from .models import Comment, Newsletter, Post


class CommentForm(forms.ModelForm):
    """Form for submitting comments"""
    
    class Meta:
        model = Comment
        fields = ['name', 'email', 'website', 'content']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Name *',
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Email *',
                'required': True
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Website (optional)'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Your Comment *',
                'rows': 5,
                'required': True
            }),
        }

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if len(content) < 10:
            raise ValidationError('Comment must be at least 10 characters long.')
        return content


class NewsletterForm(forms.ModelForm):
    """Form for newsletter subscription"""
    
    class Meta:
        model = Newsletter
        fields = ['email', 'name']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your email',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your name (optional)'
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Newsletter.objects.filter(email=email, is_active=True).exists():
            raise ValidationError('This email is already subscribed.')
        return email


class SearchForm(forms.Form):
    """Form for blog search"""
    
    q = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search posts...',
            'aria-label': 'Search'
        })
    )


class PostForm(forms.ModelForm):
    """Form for creating/editing blog posts WITH tags"""
    
    # Custom field for tags input
    tags_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tags (comma-separated, e.g., django, python, web)',
            'data-role': 'tagsinput'
        }),
        help_text='Enter tags separated by commas'
    )
    
    class Meta:
        model = Post
        fields = [
            'title', 'subtitle', 'category', 'excerpt', 'content', 
            'featured_image', 'featured_image_alt', 'video_url',
            'allow_comments', 'meta_title', 'meta_description', 
            'meta_keywords'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter post title'
            }),
            'subtitle': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter subtitle (optional)'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'excerpt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief excerpt'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 15,
                'placeholder': 'Write your post content here...'
            }),
            'featured_image': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'featured_image_alt': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Alt text for image'
            }),
            'video_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'YouTube or Vimeo URL'
            }),
            'allow_comments': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'meta_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'SEO title'
            }),
            'meta_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'SEO description'
            }),
            'meta_keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Keywords separated by commas'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate tags_input field if editing existing post
        if self.instance and self.instance.pk:
            self.fields['tags_input'].initial = ', '.join(
                tag.name for tag in self.instance.tags.all()
            )
    
    def save(self, commit=True):
        instance = super().save(commit=commit)
        
        # Handle tags
        if commit:
            # Clear existing tags
            instance.tags.clear()
            
            # Add new tags
            tags_input = self.cleaned_data.get('tags_input', '')
            if tags_input:
                tag_list = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
                instance.tags.add(*tag_list)
        
        return instance