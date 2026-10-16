from rest_framework import serializers


class IdentityRequestSerializer(serializers.Serializer):
    profile_api_token = serializers.CharField(help_text="Helsinki-profiili API token of the logged-in user.")


class IdentityResponseSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
