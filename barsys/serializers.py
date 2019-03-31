from rest_framework import serializers

from barsys.models import Purchase, User, Product


class PurchaseSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(many=False, read_only=True, slug_field='display_name')

    class Meta:
        model = Purchase
        exclude = ('invoice',)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'display_name', 'is_favorite']


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields = '__all__'
