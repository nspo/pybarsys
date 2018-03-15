from django.db import migrations, models
from django.db.models.expressions import F


def add_payments_to_old_invoices(apps, schema_editor):
    User = apps.get_model('barsys', 'User')
    Invoice = apps.get_model('barsys', 'Invoice')
    Payment = apps.get_model('barsys', 'Payment')

    num_invoices_changed = 0
    num_invoices_created = 0

    for user in User.objects.all():
        invoices = Invoice.objects.filter(recipient=user).order_by('created_date')

        # go from oldest to newest invoice
        for invoice in invoices:
            # get all (unbilled) payments older than invoice and add them to it
            relevant_payments = Payment.objects.filter(invoice=None, user=user, created_date__lte=invoice.created_date)
            total_amount = relevant_payments.aggregate(total_amount=models.Sum(F("amount"))).get("total_amount")
            if total_amount is not None:
                invoice.amount_payments += total_amount
            # even if payment_amount is None/0, mark payments as invoiced

            relevant_payments.update(invoice=invoice)
            invoice.save()
            num_invoices_changed += 1


        unbilled_payments = Payment.objects.filter(user=user, invoice=None)
        if unbilled_payments.exists():
            # user still has unbilled payments
            # create an invoice with all unbilled payments and a created_date of the newest payments

            invoice = Invoice()
            invoice.recipient = user

            invoice.amount_purchases = 0
            invoice.amount_payments = 0
            invoice.save()  # Save so that an ID is created

            invoice.created_date = unbilled_payments.order_by("-created_date")[0].created_date

            total_amount = unbilled_payments.aggregate(total_amount=models.Sum(F("amount"))).get("total_amount")
            if total_amount is not None:
                invoice.amount_payments += total_amount

            unbilled_payments.update(invoice=invoice)

            invoice.save()

            num_invoices_created += 1

            print("-- Generated invoice for {} with {} in unbilled payments".format(invoice.recipient.display_name,
                                                                           invoice.amount_payments))

    if (num_invoices_created > 0 or num_invoices_changed > 0):
        print("-- Generated {} and changed {} invoice(s)".format(num_invoices_created, num_invoices_changed))


class Migration(migrations.Migration):
    dependencies = [
        ('barsys', '0054_auto_20180304_1242'),
    ]

    operations = [
        migrations.RunPython(add_payments_to_old_invoices),
    ]
