from django.test import TransactionTestCase

from barsys.models import *


class InvoiceTestCase(TransactionTestCase):
    def setUp(self):
        u1 = User.objects.create_user("user1@example.com", "user1")
        u2 = User.objects.create_user("user2@example.com", "user2")

        u3 = User.objects.create_user("user3@example.com", "user3")
        u3.purchases_paid_by_other = u2
        u3.save()

        cat1 = Category.objects.create(name="Softdrinks")
        prod1 = Product.objects.create(category=cat1, name="Cola", price='1.05', amount="0.5 l")
        prod2 = Product.objects.create(category=cat1, name="Club-Mate", price='0.95', amount="0.5 l")

    def test_basic_invoicing(self):
        u1 = User.objects.get(display_name="user1")
        u2 = User.objects.get(display_name="user2")

        u3 = User.objects.get(display_name="user3")

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

        payment1 = Payment(user=u2, amount=Decimal('4.20'))
        payment1.save()
        self.assertEqual(u2.account_balance(), Decimal('-30'))

        payment2 = Payment(user=u2, amount=Decimal('-3.33'))
        payment2.save()
        self.assertEqual(u2.account_balance(), Decimal('-33.33'))

        self.assertEqual(u3.account_balance(), Decimal('0'))

    def test_dependant_invoicing(self):
        u1 = User.objects.get(display_name="user1")
        u2 = User.objects.get(display_name="user2")

        u3 = User.objects.get(display_name="user3")

        prod_data = dict(product_category="cat", product_name="prod",
                         product_price=Decimal('1'), product_amount="1 l")

        for i in range(1, 10):
            for u in u1, u2, u3:
                Purchase(user=u, quantity=i, **prod_data).save()

        self.assertEqual(u1.account_balance(), Decimal('0'))
        self.assertEqual(u2.account_balance(), Decimal('0'))
        self.assertEqual(u3.account_balance(), Decimal('0'))

        bal = Decimal('-45')

        self.assertEqual(u1.purchases().sum_cost(), -bal)
        self.assertEqual(u2.purchases().sum_cost(), -bal)
        self.assertEqual(u3.purchases().sum_cost(), -bal)

        i1 = Invoice.objects.create_for_user(u1)
        i2 = Invoice.objects.create_for_user(u2)

        with self.assertRaises(IntegrityError):
            # invoice for dependant not possible
            i3 = Invoice.objects.create_for_user(u3)

        u2_bal = 2 * bal

        self.assertEqual(u1.account_balance(), bal)
        self.assertEqual(u2.account_balance(), u2_bal)
        self.assertEqual(u3.account_balance(), Decimal('0'))

        Payment(user=u1, amount=Decimal('10')).save()
        Payment(user=u2, amount=Decimal('10')).save()
        Payment(user=u3, amount=Decimal('10')).save()

        self.assertEqual(u1.account_balance(), bal + Decimal('10'))
        self.assertEqual(u2.account_balance(), u2_bal + Decimal('10'))
        self.assertEqual(u3.account_balance(), Decimal('0') + Decimal('10'))
