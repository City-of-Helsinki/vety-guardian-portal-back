from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """
    Abstract base class that adds created_at and updated_at fields to models.
    https://www.geeksforgeeks.org/how-to-add-created-at-and-updated-at-fields-to-all-django-models-using-timestampedmodel/
    https://github.com/HackSoftware/Django-Styleguide?tab=readme-ov-file#base-model
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        self.updated_at = timezone.now()

        super().save(*args, **kwargs)
