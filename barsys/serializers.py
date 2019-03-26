from rest_framework import serializers

from barsys.models import Purchase, User, Product


class PurchaseSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    invoice = serializers.StringRelatedField()

    class Meta:
        model = Purchase
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'display_name', 'is_favorite']


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields = '__all__'
