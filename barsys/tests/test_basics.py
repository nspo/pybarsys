from django.test import TransactionTestCase

from barsys.models import *


class InvoiceTestCase(TransactionTestCase):
    def setUp(self):
        u1 = User.objects.create_user("user1@example.com", "user1")
        u2 = User.objects.create_user("user2@example.com", "user2")

        u3 = User.objects.create_user("user3@example.com", "user3")
        u3.purchases_paid_by_other = u2
        u3.save()

        u4 = User.objects.create_user("user4@example.com", "user4")

        cat1 = Category.objects.create(name="Softdrinks")
        prod1 = Product.objects.create(category=cat1, name="Cola", price='1.05', amount="0.5 l")
        prod2 = Product.objects.create(category=cat1, name="Club-Mate", price='0.95', amount="0.5 l")
        prod3 = Product.objects.create(category=cat1, name="OJ", price='0.90', amount="0.3 l")

        self.prod_data = dict(product_category="cat", product_name="prod",
                              product_price=Decimal('1'), product_amount="1 l")

    def test_basic_invoicing(self):
        u1 = User.objects.get(display_name="user1")
        u2 = User.objects.get(display_name="user2")

        u3 = User.objects.get(display_name="user3")

        cat1 = Category.objects.get(name="Softdrinks")
        prod1 = Product.objects.get(name="Cola")
        prod2 = Product.objects.get(name="Club-Mate")

        with self.assertRaises(ValidationError):
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

        with self.assertRaises(ValidationError):
            purch = u1.purchases()[0]
            purch.product_name = "something else"
            purch.save()

        with self.assertRaises(ValidationError):
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

        self.assertEqual(u2.account_balance(), Decimal('-34.20'))
        # now make invoice that includes payment
        invoice2 = Invoice.objects.create_for_user(u2)
        self.assertEqual(u2.account_balance(), Decimal('-30'))

        payment2 = Payment(user=u2, amount=Decimal('-3.33'))
        payment2.save()
        self.assertEqual(u2.account_balance(), Decimal('-30'))

        invoice2 = Invoice.objects.create_for_user(u2)
        self.assertEqual(u2.account_balance(), Decimal('-33.33'))

        Purchase.objects.create_from_product(prod2, user=u2, quantity=3)
        Invoice.objects.create_for_user(u2)
        self.assertEqual(u2.account_balance(), Decimal('-36.18'))

        self.assertEqual(u3.account_balance(), Decimal('0'))

    def test_dependant_invoicing(self):
        u1 = User.objects.get(display_name="user1")
        u2 = User.objects.get(display_name="user2")

        u3 = User.objects.get(display_name="user3")

        for i in range(1, 10):
            for u in u1, u2, u3:
                Purchase(user=u, quantity=i, **self.prod_data).save()

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
            Invoice.objects.create_for_user(u3)

        self.assertEqual(u1.account_balance(), bal)
        self.assertEqual(u2.account_balance(), 2 * bal)
        self.assertEqual(u3.account_balance(), Decimal('0'))

        Payment(user=u1, amount=Decimal('10')).save()
        Payment(user=u2, amount=Decimal('10')).save()
        with self.assertRaises(IntegrityError):
            Payment.objects.create(user=u3, amount=Decimal('10'))

        self.assertEqual(u1.account_balance(), bal)
        self.assertEqual(u2.account_balance(), 2 * bal)
        self.assertEqual(u3.account_balance(), Decimal('0'))

        i1 = Invoice.objects.create_for_user(u1)
        i2 = Invoice.objects.create_for_user(u2)

        with self.assertRaises(IntegrityError):
            Invoice.objects.create_for_user(u3)

        self.assertEqual(u1.account_balance(), bal + Decimal('10'))
        self.assertEqual(u2.account_balance(), 2 * bal + Decimal('10'))
        self.assertEqual(u3.account_balance(), Decimal('0'))

    def test_switch_user_to_dependant(self):
        u1 = User.objects.get(display_name="user1")
        u4 = User.objects.get(display_name="user4")

        for i in range(1, 10):
            Purchase(user=u4, quantity=i, **self.prod_data).save()

        self.assertEqual(u4.account_balance(), Decimal('0'))

        Payment.objects.create(user=u4, amount=Decimal('5'))

        Invoice.objects.create_for_user(u4)

        self.assertEqual(u4.account_balance(), Decimal('-40'))

        with self.assertRaises(ValidationError):
            u4.purchases_paid_by_other = u1
            u4.save()

        u4 = User.objects.get(pk=u4.pk)

        Payment.objects.create(user=u4, amount=Decimal('39.99'))
        Invoice.objects.create_for_user(u4)

        self.assertEqual(u4.account_balance(), Decimal('-0.01'))

        with self.assertRaises(ValidationError):
            u4.purchases_paid_by_other = u1
            u4.save()

        u4 = User.objects.get(pk=u4.pk)

        Payment.objects.create(user=u4, amount=Decimal('1'))
        Invoice.objects.create_for_user(u4)
        self.assertEqual(u4.account_balance(), Decimal('0.99'))

        try:
            u4.purchases_paid_by_other = u1
            u4.save()
        except IntegrityError:
            self.fail("Could not make user a dependant although account_balance > 0")

        with self.assertRaises(IntegrityError):
            Payment.objects.create(user=u4, amount=Decimal('5'))

        with self.assertRaises(IntegrityError):
            Invoice.objects.create_for_user(u4)

        Purchase.objects.create(user=u4, quantity=2, **self.prod_data)

        self.assertEqual(u4.account_balance(), Decimal('0.99'))
        self.assertEqual(u4.purchases().sum_cost(), Decimal('47'))

        Purchase.objects.create(user=u1, quantity=3, **self.prod_data)
        self.assertEqual(u1.account_balance(), Decimal('0'))

        i = Invoice.objects.create_for_user(u1)
        self.assertEqual(u1.account_balance(), Decimal('-5'))
        self.assertEqual(i.due(), Decimal('5'))

        self.assertEqual(i.own_purchases().sum_cost(), Decimal('3'))
        self.assertEqual(i.purchases().paid_as_self(u1).sum_cost(), Decimal('3'))
        self.assertEqual(i.purchases().paid_as_other(u1).sum_cost(), Decimal('2'))

        Payment.objects.create(user=u1, amount=5)

        for i in range(1, 10):
            Purchase(user=u1, quantity=i, **self.prod_data).save()
            Purchase(user=u4, quantity=i, **self.prod_data).save()

        Payment.objects.create(user=u1, amount=50)

        i = Invoice.objects.create_for_user(u1)
        self.assertEqual(i.amount_payments, Decimal('55'))
        self.assertEqual(i.amount_purchases, Decimal('90'))

        self.assertEqual(u1.account_balance(), Decimal('-40'))

        self.assertEqual(u4.account_balance(), Decimal('0.99'))

        with self.assertRaises(ValidationError):
            u4.purchases_paid_by_other = u4
            u4.save()

    def test_switch_user_to_dependant2(self):
        u1 = User.objects.get(display_name="user1")
        u4 = User.objects.get(display_name="user4")

        Payment.objects.create(user=u4, amount=Decimal('5'))

        with self.assertRaises(ValidationError):
            u4.purchases_paid_by_other = u1
            u4.save()


class ProductAutochangeSetTestCase(TransactionTestCase):
    def setUp(self):
        cat1 = Category.objects.create(name="Softdrinks")
        Product.objects.create(category=cat1, name="Prod1", price='1', amount="0.5 l")
        Product.objects.create(category=cat1, name="Prod2", price='1', amount="0.5 l")
        Product.objects.create(category=cat1, name="Prod3", price='1', amount="0.5 l")
        Product.objects.create(category=cat1, name="Prod4", price='1', amount="0.5 l")

    def test_pac(self):
        prod1, prod2, prod3, prod4 = Product.objects.all()

        for p in [prod1, prod2, prod3, prod4]:
            self.assertTrue(p.is_active)
            self.assertFalse(p.is_bold)

        pac1 = ProductAutochange(product=prod1, change_active=ProductAutochange.CHANGE_TO_NO,
                                 change_bold=ProductAutochange.CHANGE_TO_YES)
        pac1.execute()

        self.assertFalse(prod1.is_active)
        self.assertTrue(prod1.is_bold)

        for p in [prod2, prod3, prod4]:
            self.assertTrue(p.is_active)
            self.assertFalse(p.is_bold)

        pac2 = ProductAutochange(product=prod2, change_active=ProductAutochange.CHANGE_TO_NO)
        pac2.execute()

        self.assertFalse(prod2.is_active)
        self.assertFalse(prod2.is_bold)

    def test_pacs1(self):
        prod1, prod2, prod3, prod4 = Product.objects.all()

        for p in [prod1, prod2, prod3, prod4]:
            self.assertTrue(p.is_active)
            self.assertFalse(p.is_bold)

        pacs1 = ProductAutochangeSet.objects.create(title="pacs1")

        pac1 = ProductAutochange.objects.create(pc_set=pacs1, product=prod1,
                                                change_active=ProductAutochange.CHANGE_TO_NO,
                                                change_bold=ProductAutochange.CHANGE_TO_YES)
        pac2 = ProductAutochange.objects.create(pc_set=pacs1, product=prod2,
                                                change_active=ProductAutochange.CHANGE_TO_NO)

        pacs1.execute()

        for p in [prod1, prod2, prod3, prod4]:
            p.refresh_from_db()

        self.assertFalse(prod1.is_active)
        self.assertTrue(prod1.is_bold)
        self.assertFalse(prod2.is_active)
        self.assertFalse(prod2.is_bold)
        for p in [prod3, prod4]:
            self.assertTrue(p.is_active)
            self.assertFalse(p.is_bold)

    def test_pacs2(self):
        prod1, prod2, prod3, prod4 = Product.objects.all()

        for p in [prod1, prod2, prod3, prod4]:
            self.assertTrue(p.is_active)
            self.assertFalse(p.is_bold)

        pacs1 = ProductAutochangeSet.objects.create(title="pacs1", change_others_active=ProductAutochange.CHANGE_TO_NO,
                                                    change_others_bold=ProductAutochange.CHANGE_TO_YES)

        pac1 = ProductAutochange.objects.create(pc_set=pacs1, product=prod1,
                                                change_active=ProductAutochange.CHANGE_TO_YES,
                                                change_bold=ProductAutochange.NO_CHANGE)
        pac3 = ProductAutochange.objects.create(pc_set=pacs1, product=prod3,
                                                change_active=ProductAutochange.CHANGE_TO_YES)

        pacs1.execute()

        for p in [prod1, prod2, prod3, prod4]:
            p.refresh_from_db()

        self.assertEqual(prod1.is_active, True)
        self.assertEqual(prod2.is_active, False)
        self.assertEqual(prod3.is_active, True)
        self.assertEqual(prod4.is_active, False)

        self.assertEqual(prod1.is_bold, False)
        self.assertEqual(prod2.is_bold, True)
        self.assertEqual(prod3.is_bold, False)
        self.assertEqual(prod4.is_bold, True)
