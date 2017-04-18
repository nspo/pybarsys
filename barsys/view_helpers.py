from .models import StatsDisplay, Purchase
from django.utils import timezone
from django.contrib import messages

from django.template.loader import render_to_string
from django.core.mail import send_mail, EmailMultiAlternatives
from decimal import Decimal
from constance import config
from pybarsys import settings as pybarsys_settings
from itertools import groupby
from collections import OrderedDict



def get_renderable_stats_elements():
    """Create a list of dicts for all StatsDisplays that can be rendered by view more easily"""
    stats_elements = []

    all_displays = StatsDisplay.objects.order_by("-show_by_default")
    for index, stat in enumerate(all_displays):
        stats_element = {"stats_id": "stats_{}".format(stat.pk),
                         "show_by_default": stat.show_by_default,
                         "title": stat.title}

        # construct query filters step by step
        filters = {}
        if stat.filter_category:
            filters["product_category"] = stat.filter_category.name
        if stat.filter_product:
            filters["product_name"] = stat.filter_product.name

        # filter by timedelta
        filters["created_date__gte"] = timezone.now() - stat.time_period

        stats_element["rows"] = []
        if stat.sort_by_and_show == StatsDisplay.SORT_BY_NUM_PURCHASES:
            top_five = Purchase.objects.filter(**filters).stats_purchases_by_user(limit=5)
            for user, total_quantity in top_five:
                stats_element["rows"].append({"left": "{}x".format(total_quantity),
                                              "right": "{} {}".format(stat.row_string, user.display_name)})
        else:
            top_five = Purchase.objects.filter(**filters).stats_cost_by_user(limit=5)
            for u_index, (user, total_cost) in enumerate(top_five):
                stats_element["rows"].append({"left": "{}.".format(u_index + 1),
                                              "right": "{} {}".format(stat.row_string, user.display_name)})

        if index + 1 < len(all_displays):
            # toggle next one on
            stats_element["toggle_other_on"] = "stats_{}".format(all_displays[index + 1].pk)
        else:
            # toggle first one on
            stats_element["toggle_other_on"] = "stats_{}".format(all_displays[0].pk)
        # if there is only one display, it's toggled off and on again with one click

        stats_elements.append(stats_element)

    return stats_elements


def send_invoice_mails(request, invoices):
    """ Send invoice mails to invoice recipients with a list of all purchases of that invoice """
    num_invoice_mail_success = 0
    invoice_mail_failure = []  # [(username, error), ...]
    for invoice in invoices:
        context = {}
        context["invoice"] = invoice
        context["config"] = config
        context["own_purchases"] = invoice.own_purchases()
        context["other_purchases_grouped"] = invoice.other_purchases_grouped()
        context["last_invoices"] = invoice.recipient.invoices()[:5]
        context["last_payments"] = invoice.recipient.payments()[:5]
        content_plain = render_to_string("email/normal_invoice.plaintext.html", context)
        content_html = render_to_string("email/normal_invoice.html.html", context)
        try:
            msg = EmailMultiAlternatives(config.MAIL_INVOICE_SUBJECT, content_plain,
                                         pybarsys_settings.EMAIL_FROM_ADDRESS, [invoice.recipient.email],
                                         reply_to=[config.MAIL_CONTACT_EMAIL])
            msg.attach_alternative(content_html, "text/html")
            msg.send(fail_silently=False)

            num_invoice_mail_success += 1
        except Exception as e:
            invoice_mail_failure.append((invoice.recipient, e))

    if num_invoice_mail_success > 0:
        messages.info(request, "{} invoice mails were successfully sent. ".format(num_invoice_mail_success))
    if len(invoice_mail_failure) > 0:
        messages.error(request, "Sending invoice mail(s) to the following user(s) failed: {}".
                       format(", ".join(["{} ({})".format(u, err) for u, err in invoice_mail_failure])))


def send_reminder_mails(request, users):
    """ Send payment reminder mails to users """
    num_reminder_mail_success = 0
    reminder_mail_failure = []  # [(username, error), ...]
    for user in users:
        context = {}
        context["user"] = user
        context["config"] = config
        context["last_invoices"] = user.invoices()[:5]
        context["last_payments"] = user.payments()[:5]
        content_plain = render_to_string("email/payment_reminder.plaintext.html", context)
        content_html = render_to_string("email/payment_reminder.html.html", context)
        try:
            msg = EmailMultiAlternatives(config.MAIL_PAYMENT_REMINDER_SUBJECT, content_plain,
                                         pybarsys_settings.EMAIL_FROM_ADDRESS, [user.email],
                                         reply_to=[config.MAIL_CONTACT_EMAIL])
            msg.attach_alternative(content_html, "text/html")
            msg.send(fail_silently=False)

            num_reminder_mail_success += 1
        except Exception as e:
            reminder_mail_failure.append((user, e))

    if num_reminder_mail_success > 0:
        messages.info(request, "{} payment reminders were successfully sent. ".format(num_reminder_mail_success))
    if len(reminder_mail_failure) > 0:
        messages.error(request, "Sending payment reminder mail(s) to the following user(s) failed: {}". \
                       format(", ".join(["{} ({})".format(u, err) for u, err in reminder_mail_failure])))


def group_users(ungrouped_users):
    grouped_users = OrderedDict()
    for k, g in groupby(ungrouped_users, key=lambda u: u.display_name[0].upper()):
        if k in grouped_users:
            grouped_users[k] += g
        else:
            grouped_users[k] = list(g)
    return grouped_users

def get_jump_to_data_lines(all_users):
    letter_groups_by_line = []
    # create letter_groups for jumping to existing users in view
    letter_group = OrderedDict()
    letter_group["A - C"] = ['A', 'B', 'C']
    letter_group["D - F"] = ['D', 'E', 'F']
    letter_group["G - I"] = ['G', 'H', 'I']
    letter_groups_by_line.append(letter_group)

    letter_group = OrderedDict()
    letter_group["J - L"] = ['J', 'K', 'L']
    letter_group["M - O"] = ['M', 'N', 'O']
    letter_groups_by_line.append(letter_group)

    letter_group = OrderedDict()
    letter_group["P - S"] = ['P', 'Q', 'R', 'S']
    letter_group["T - V"] = ['T', 'U', 'V']
    letter_group["W - Z"] = ['W', 'X', 'Y', 'Z']
    letter_groups_by_line.append(letter_group)

    # Where the button for this group should jump to
    jump_to_data_lines = []

    for line in letter_groups_by_line:
        this_line = []
        for index_group, (title, letters) in enumerate(line.items()):
            for index_letter, letter in enumerate(letters):
                if letter in all_users:
                    # print("{} in {}, so choosing {}".format(letter, group, letter))
                    this_line.append((title, letter))
                    break
                elif index_letter + 1 == len(letters):
                    # print("{} not in {}, so choosing {}".format(letter, group, group[0]))
                    this_line.append((title, letters[0]))
                    break
        jump_to_data_lines.append(this_line)

    return jump_to_data_lines
