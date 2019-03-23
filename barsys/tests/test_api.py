from django.test import TransactionTestCase, Client
from rest_framework import status
from rest_framework.utils import json

from barsys.models import *
from barsys.serializers import *


class ApiTestCase(TransactionTestCase):
    client = Client()

    def setUp(self):
        self.client = Client()
        self.u1 = User.objects.create_user("user1@example.com", "user1")
        u2 = User.objects.create_user("user2@example.com", "user2")

        u3 = User.objects.create_user("user3@example.com", "user3")
        u3.purchases_paid_by_other = u2
        u3.save()

        u4 = User.objects.create_user("user4@example.com", "user4")

        cat1 = Category.objects.create(name="Softdrinks")
        self.prod1 = Product.objects.create(category=cat1, name="Cola", price='1.05', amount="0.5 l")
        prod2 = Product.objects.create(category=cat1, name="Club-Mate", price='0.95', amount="0.5 l")
        prod3 = Product.objects.create(category=cat1, name="OJ", price='0.90', amount="0.3 l")

        purch1 = Purchase.objects.create(user=self.u1, product_category=self.prod1.category.name,
                                         product_name=self.prod1.name, product_price=self.prod1.price,
                                         product_amount=self.prod1.amount, quantity=1)
        purch2 = Purchase.objects.create(user=u2, product_category=prod2.category.name, product_name=prod2.name,
                                         product_price=prod2.price, product_amount=prod2.amount, quantity=3)

        self.prod_data = dict(product_category="cat", product_name="prod",
                              product_price=Decimal('1'), product_amount="1 l")

    def test_get_all_users(self):
        response = self.client.get(reverse('main_user_api'))
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        self.assertEqual(response.data, serializer.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_all_products(self):
        response = self.client.get(reverse('main_product_api'))
        products = Product.objects.all()
        serializer = ProductSerializer(products, many=True)
        self.assertEqual(response.data, serializer.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_all_purchases(self):
        response = self.client.get(reverse('main_purchase_api'))
        purchases = Purchase.objects.all()
        serializer = PurchaseSerializer(purchases, many=True)
        self.assertEqual(response.data, serializer.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_post_purchase(self):
        json_purchase = {
            "user_id": self.u1.pk,
            "quantity": 1,
            "product_id": self.prod1.pk,
            "comment": "test_purchase"
        }
        response = self.client.post(reverse('main_purchase_api'), data=json.dumps(json_purchase),
                                    content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        serializer = PurchaseSerializer(Purchase.objects.get(id=response.data['id']))
        self.assertEqual(response.data, serializer.data)

    def test_invalid_post_purchase(self):
        json_purchase = {
            "user_id": -1,
            "quantity": 1,
            "product_id": self.prod1.pk,
            "comment": "test_purchase"
        }
        response = self.client.post(reverse('main_purchase_api'), data=json.dumps(json_purchase),
                                    content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_post_purchase_autolocked_user(self):
        self.u1.is_autolocked = True
        self.u1.save()
        json_purchase = {
            "user_id": self.u1.pk,
            "quantity": 1,
            "product_id": self.prod1.pk,
            "comment": "test_purchase"
        }
        response = self.client.post(reverse('main_purchase_api'), data=json.dumps(json_purchase),
                                    content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
