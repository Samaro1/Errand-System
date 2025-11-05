from django.db import models
from datetime import timedelta, timezone

# Create your models here.
class Errand(models.Model):
    creator = models.ForeignKey("users.Customer", on_delete=models.CASCADE, related_name="posted_errands")
    runner = models.ForeignKey("users.Customer", on_delete=models.CASCADE, related_name="taken_errands", null=True, blank=True)
    title = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.DurationField(default=timedelta(hours=2))
    created_at = models.DateTimeField(auto_now_add=True)
    approved= models.BooleanField(default=False)
    
    status = models.CharField(
        max_length=20,
        default="pending",  # pending → active → awaiting_approval → completed → refunded
    )

    def has_expired(self):
        end_time = self.created_at + self.duration
        return timezone.now() > end_time

    def __str__(self):
        return f"{self.title} ({self.status})"


class Review(models.Model):
    # who is being reviewed
    runner = models.ForeignKey("users.Customer", on_delete=models.CASCADE, related_name="reviews_received")
    # who wrote the review
    reviewer = models.ForeignKey("users.Customer", on_delete=models.CASCADE, related_name="reviews_given")
    # link the review to the errand
    errand = models.ForeignKey("errands.Errand", on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()  # e.g., 1–5 stars
    feedback = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.reviewer.username} for {self.runner.username} - {self.rating}⭐"
