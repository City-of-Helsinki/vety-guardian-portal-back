from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    """
    Internal user account.
    Authentication method may change later without impacting the rest of the application.
    """

    # suomifi_identifier = models.CharField(max_length=255, unique=True, null=True, blank=True)
    # email = models.EmailField(unique=True)

    def __str__(self):
        return self.username
