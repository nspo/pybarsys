from django.db import migrations, models
from django.db.models.expressions import F


def create_invoice_for_unbilled_payments(apps, schema_editor):
    User = apps.get_model('barsys', 'User')
    Invoice = apps.get_model('barsys', 'Invoice')
    Payment = apps.get_model('barsys', 'Payment')

    num_invoices = 0
    for user in User.objects.all():
        unbilled_payments = Payment.objects.filter(user=user, invoice=None)
        if unbilled_payments.count() > 0:
            # has unbilled payments

            invoice = Invoice()
            invoice.recipient = user

            invoice.amount_purchases = 0
            invoice.amount_payments = 0
            invoice.save()  # Save so that an ID is created

            # Check non-invoiced payments
            total_amount = unbilled_payments.aggregate(total_amount=models.Sum(F("amount"))).get("total_amount")
            if total_amount is not None:
                invoice.amount_payments += total_amount

            unbilled_payments.update(invoice=invoice)

            invoice.save()

            num_invoices += 1
            print("-- Generated invoice for {} with {} in payments".format(invoice.recipient.display_name,
                                                                           invoice.amount_payments))

    if (num_invoices > 0):
        print("-- Generated {} invoice(s)".format(num_invoices))


class Migration(migrations.Migration):
    dependencies = [
        ('barsys', '0054_auto_20180304_1242'),
    ]

    operations = [
        migrations.RunPython(create_invoice_for_unbilled_payments),
    ]
