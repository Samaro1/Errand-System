from rest_framework import serializers
from .models import Errand, Review


class ErrandSerializer(serializers.ModelSerializer):
    # Optional: show creator and runner usernames instead of their object IDs
    creator = serializers.StringRelatedField(read_only=True)
    runner = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Errand
        fields = [
            "id",
            "creator",
            "runner",
            "title",
            "description",
            "price",
            "duration",
            "created_at",
            "approved",
            "status",
            "has_expired",
        ]
        read_only_fields = ["created_at", "approved", "status", "has_expired"]

    def create(self, validated_data):
        """Attach the creator automatically when creating an errand."""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["creator"] = request.user
        return super().create(validated_data)


class ReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.StringRelatedField(read_only=True)
    runner = serializers.StringRelatedField(read_only=True)
    errand = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "reviewer",
            "runner",
            "errand",
            "rating",
            "feedback",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def create(self, validated_data):
        """Automatically attach the reviewer."""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["reviewer"] = request.user
        return super().create(validated_data)