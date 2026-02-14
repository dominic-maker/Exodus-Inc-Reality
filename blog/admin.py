from blog.models import BlogPost

latest_posts = BlogPost.objects.all()[:3]

