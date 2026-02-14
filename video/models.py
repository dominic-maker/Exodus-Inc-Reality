from django.db import models
from listings.models import Listing

# Create your models here.
class Video(models.Model):
    Listing = models.ForeignKey('Listing', related_name='videos', on_delete=models.CASCADE)
    video_file = models.FileField(upload_to='videos/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Video for {self.listing.title}"
