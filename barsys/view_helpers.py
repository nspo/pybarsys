import os.path
from collections import OrderedDict
from itertools import groupby

from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from pybarsys import settings as pybarsys_settings
from pybarsys.settings import PybarsysPreferences
from .models import StatsDisplay, Purchase


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
        if stat.filter_by_category.all().count() > 0:
            filters["product_category__in"] = [c.name for c in stat.filter_by_category.all()]

        if stat.filter_by_product.all().count() > 0:
            filters["product_name__in"] = [p.name for p in stat.filter_by_product.all()]

        # filter by time
        filters["created_date__gte"] = stat.time_period_begin()

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


def send_invoice_mails(request, invoices, send_dependant_notifications=False):
    """ Send invoice mails to invoice recipients with a list of all purchases of that invoice.
        Optionally send purchase notifications to users whose purchases are paid by someone else.
    """
    num_invoice_mail_success = 0
    invoice_mail_failure = []  # [(username, error), ...]

    num_purchase_notif_mail_success = 0
    purchase_notif_mail_failure = []

    for invoice in invoices:
        context = {}
        context["pybarsys_preferences"] = PybarsysPreferences
        context["invoice"] = invoice
        context["recipient"] = invoice.recipient
        context["own_purchases"] = invoice.own_purchases()
        context["other_purchases_grouped"] = invoice.other_purchases_grouped()
        context["last_invoices"] = invoice.recipient.invoices()[:5]
        context["last_payments"] = invoice.recipient.payments()[:5]
        content_plain = render_to_string(
            os.path.join(PybarsysPreferences.EMAIL.TEMPLATE_DIR, "normal_invoice.plaintext.html"
                         ), context)
        content_html = render_to_string(
            os.path.join(PybarsysPreferences.EMAIL.TEMPLATE_DIR, "normal_invoice.html.html"),
            context)
        try:
            msg = EmailMultiAlternatives(PybarsysPreferences.EMAIL.INVOICE_SUBJECT, content_plain,
                                         pybarsys_settings.EMAIL_FROM_ADDRESS, [invoice.recipient.email],
                                         reply_to=[PybarsysPreferences.EMAIL.CONTACT_EMAIL])
            msg.attach_alternative(content_html, "text/html")
            msg.send(fail_silently=False)

            num_invoice_mail_success += 1
        except Exception as e:
            invoice_mail_failure.append((invoice.recipient, e))

        if send_dependant_notifications and invoice.has_dependant_purchases():
            # send purchase notifications to dependants
            for dependant, purchases in invoice.other_purchases_grouped():
                notif_context = {}
                notif_context["pybarsys_preferences"] = PybarsysPreferences
                notif_context["invoice"] = invoice
                notif_context["dependant"] = dependant
                notif_context["purchases"] = purchases
                content_plain = render_to_string(os.path.join(PybarsysPreferences.EMAIL.TEMPLATE_DIR,
                                                              "dependant_notification.plaintext.html"), notif_context)
                content_html = render_to_string(os.path.join(PybarsysPreferences.EMAIL.TEMPLATE_DIR,
                                                             "dependant_notification.html.html"), notif_context)
                try:
                    msg = EmailMultiAlternatives(PybarsysPreferences.EMAIL.PURCHASE_NOTIFICATION_SUBJECT, content_plain,
                                                 pybarsys_settings.EMAIL_FROM_ADDRESS, [dependant.email],
                                                 reply_to=[PybarsysPreferences.EMAIL.CONTACT_EMAIL])
                    msg.attach_alternative(content_html, "text/html")
                    msg.send(fail_silently=False)

                    num_purchase_notif_mail_success += 1
                except Exception as e:
                    purchase_notif_mail_failure.append((dependant, e))

    if num_invoice_mail_success > 0:
        messages.info(request, "{} invoice mails were successfully sent. ".format(num_invoice_mail_success))
    if len(invoice_mail_failure) > 0:
        messages.error(request, "Sending invoice mail(s) to the following user(s) failed: {}".
                       format(", ".join(["{} ({})".format(u, err) for u, err in invoice_mail_failure])))

    if num_purchase_notif_mail_success > 0:
        messages.info(request, "{} dependant notification mails were successfully sent. ".format(
            num_purchase_notif_mail_success))
    if len(purchase_notif_mail_failure) > 0:
        messages.error(request, "Sending dependant notification mail(s) to the following user(s) failed: {}".
                       format(", ".join(["{} ({})".format(u, err) for u, err in purchase_notif_mail_failure])))


def send_reminder_mails(request, users):
    """ Send payment reminder mails to users """
    num_reminder_mail_success = 0
    reminder_mail_failure = []  # [(username, error), ...]
    for user in users:
        context = {}
        context["pybarsys_preferences"] = PybarsysPreferences
        context["user"] = user
        context["recipient"] = user
        context["last_invoices"] = user.invoices()[:5]
        context["last_payments"] = user.payments()[:5]
        content_plain = render_to_string(
            os.path.join(PybarsysPreferences.EMAIL.TEMPLATE_DIR, "payment_reminder.plaintext.html"),
            context)
        content_html = render_to_string(
            os.path.join(PybarsysPreferences.EMAIL.TEMPLATE_DIR, "payment_reminder.html.html"),
            context)
        try:
            msg = EmailMultiAlternatives(PybarsysPreferences.EMAIL.PAYMENT_REMINDER_SUBJECT, content_plain,
                                         pybarsys_settings.EMAIL_FROM_ADDRESS, [user.email],
                                         reply_to=[PybarsysPreferences.EMAIL.CONTACT_EMAIL])
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
    """ Group users by first letter of name """
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
