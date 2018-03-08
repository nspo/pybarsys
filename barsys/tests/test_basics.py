from django.test import TransactionTestCase

from barsys.models import *


class InvoiceTestCase(TransactionTestCase):
    def setUp(self):
        u1 = User.objects.create_user("user1@example.com", "user1")
        u2 = User.objects.create_user("user2@example.com", "user2")
        cat1 = Category.objects.create(name="Softdrinks")
        prod1 = Product.objects.create(category=cat1, name="Cola", price='1.05', amount="0.5 l")
        prod2 = Product.objects.create(category=cat1, name="Club-Mate", price='0.95', amount="0.5 l")

    def test_basic_invoicing(self):
        u1 = User.objects.get(display_name="user1")
        u2 = User.objects.get(display_name="user2")
        cat1 = Category.objects.get(name="Softdrinks")
        prod1 = Product.objects.get(name="Cola")
        prod2 = Product.objects.get(name="Club-Mate")

        with self.assertRaises(IntegrityError):
            p1 = Purchase()
            p1.save()

        # no invoice or purchases yet
        self.assertEqual(u1.account_balance(), Decimal('0'))

        for i in range(1, 10):
            Purchase(
                user=u1, product_category=cat1.name, product_name=prod1.name,
                product_price=prod1.price, product_amount=prod1.amount,
                quantity=i
            ).save()

            Purchase(
                user=u2, product_category=cat1.name, product_name=prod2.name,
                product_price=prod2.price, product_amount=prod2.amount,
                quantity=i
            ).save()

        # no invoice yet
        self.assertEqual(u1.account_balance(), Decimal('0'))
        self.assertEqual(u2.account_balance(), Decimal('0'))

        invoice1 = Invoice.objects.create_for_user(u1)

        self.assertEqual(u1.account_balance(), Decimal('-47.25'))
        self.assertEqual(u2.account_balance(), Decimal('0'))

        invoice1_empty = Invoice.objects.create_for_user(u1)  # should have 0$
        self.assertEqual(u1.account_balance(), Decimal('-47.25'))

        invoice2 = Invoice.objects.create_for_user(u2)
        self.assertEqual(u2.account_balance(), Decimal('-42.75'))

        with self.assertRaises(IntegrityError):
            purch = u1.purchases()[0]
            purch.product_name = "something else"
            purch.save()

        with self.assertRaises(Exception):
            purch = u2.purchases()[0]
            purch.product_price = Decimal('0')
            purch.save()

        try:
            invoice2.delete()
            purch = u2.purchases()[0]
            purch.delete()
        except IntegrityError:
            self.fail("Should be able to delete purchase again after deleting invoice")

        invoice2 = Invoice.objects.create_for_user(u2)
        self.assertEqual(u2.account_balance(), Decimal('-34.20'))
