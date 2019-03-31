from rest_framework import serializers

from barsys.models import Purchase, User, Product


class PurchaseSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = Purchase
        fields = ['id', 'user', 'product_category', 'product_name', 'product_price', 'product_amount', 'quantity',
                  'comment', 'is_free_item_purchase', 'free_item_description', 'created_date', 'modified_date']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'display_name', 'is_favorite']


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields = '__all__'
