import os.path
from collections import OrderedDict
from itertools import groupby

from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone

from pybarsys import settings as pybarsys_settings
from pybarsys.settings import PybarsysPreferences
from .models import StatsDisplay, Purchase, Invoice, Product


def get_renderable_stats_elements():
    """Create a list of dicts for all StatsDisplays that can be rendered by view more easily"""
    stats_elements = []

    all_displays = StatsDisplay.objects.order_by("-show_by_default")
    if PybarsysPreferences.Misc.SHUFFLE_STATSDISPLAY_ORDER:
        all_displays = all_displays.order_by("?")

    for index, stat in enumerate(all_displays):
        stats_element = {"stats_id": "stats_{}".format(stat.pk),
                         "show_by_default": stat.show_by_default,
                         "title": stat.title}

        if PybarsysPreferences.Misc.SHUFFLE_STATSDISPLAY_ORDER:
            # always show the StatsDisplay that is at the start first, irrespective of show_by_default, b/c
            # result has been shuffled already
            if index == 0:
                stats_element["show_by_default"] = True
            else:
                stats_element["show_by_default"] = False

        # construct query filters step by step
        filters = {}
        if stat.filter_by_category.all().exists():
            filters["product_category__in"] = [c["name"] for c in stat.filter_by_category.values("name")]

        if stat.filter_by_product.all().exists():
            filters["product_name__in"] = [p["name"] for p in stat.filter_by_product.values("name")]

        # filter by time
        filters["created_date__gte"] = stat.time_period_begin()

        stats_element["rows"] = []
        if stat.sort_by_and_show == StatsDisplay.SORT_BY_NUM_PURCHASES:
            top_users = Purchase.objects.filter(**filters).stats_purchases_by_user(
                limit=PybarsysPreferences.Misc.NUM_MAIN_USERS_IN_STATSDISPLAY)
            for user, total_quantity in top_users:
                stats_element["rows"].append({"left": "{}x".format(total_quantity),
                                              "row_string": stat.row_string,
                                              "user_name": user.display_name,
                                              "user_id": user.id})
        else:
            top_users = Purchase.objects.filter(**filters).stats_cost_by_user(
                limit=PybarsysPreferences.Misc.NUM_MAIN_USERS_IN_STATSDISPLAY)
            for u_index, (user, total_cost) in enumerate(top_users):
                stats_element["rows"].append({"left": "{}.".format(u_index + 1),
                                              "row_string": stat.row_string,
                                              "user_name": user.display_name,
                                              "user_id": user.id})

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
        context["payments"] = invoice.payments()

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
    letter_group["A B C"] = ['A', 'B', 'C']
    letter_group["D E F"] = ['D', 'E', 'F']
    letter_group["G H I"] = ['G', 'H', 'I']
    letter_groups_by_line.append(letter_group)

    letter_group = OrderedDict()
    letter_group["J K L"] = ['J', 'K', 'L']
    letter_group["M N O"] = ['M', 'N', 'O']
    letter_groups_by_line.append(letter_group)

    letter_group = OrderedDict()
    letter_group["P Q R S"] = ['P', 'Q', 'R', 'S']
    letter_group["T U V"] = ['T', 'U', 'V']
    letter_group["W X Y Z"] = ['W', 'X', 'Y', 'Z']
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


def get_most_bought_product_in_queryset(purchase_query_set):
    # Try to get the product bought most often in purchase_query_set that is currently available to buy

    most_bought_products = purchase_query_set.values("product_name", "product_amount").order_by().annotate(
        models.Count("product_name"), num_purchases=models.Count("product_amount")).order_by("-num_purchases")
    for prod in most_bought_products:
        if Product.objects.active().filter(name=prod["product_name"], amount=prod["product_amount"]).exists():
            return prod
            # else continue
    return None  # None found or None still available


def get_most_bought_product_in_time(hours):
    return get_most_bought_product_in_queryset(
        Purchase.objects.filter(created_date__gte=timezone.now() - timezone.timedelta(hours=hours)))


def get_most_bought_product_for_user(user):
    most_bought_product = None
    if user.purchases().unbilled().exists():
        # most bought product of unbilled purchases
        most_bought_product = get_most_bought_product_in_queryset(user.purchases().unbilled())

    if most_bought_product is None and Invoice.objects.filter(purchase__user=user).distinct().exists():
        # most bought product by this user on last invoice that had a purchase of him/her
        # works both when user pays themselves and when not
        most_bought_product = get_most_bought_product_in_queryset(
            Invoice.objects.filter(purchase__user=user).distinct()[0].purchases().filter(user=user))

    if most_bought_product is None:
        # user has no purchases yet, just use all purchases of last 4 hours
        most_bought_product = get_most_bought_product_in_time(hours=4)

    if most_bought_product is None:
        # okay, so maybe last 24 hours?
        most_bought_product = get_most_bought_product_in_time(hours=24)

    if most_bought_product is None:
        # Found none :(
        most_bought_product = {'product_amount': '', 'product_name': ''}

    return most_bought_product


def get_most_bought_product_for_users(users):
    most_bought_product = None
    if users.purchases().unbilled().exists():
        # most bought product of unbilled purchases
        most_bought_product = get_most_bought_product_in_queryset(users.purchases().unbilled())

    if most_bought_product is None:
        # Show most bought product of last 4 hours
        most_bought_product = get_most_bought_product_in_time(4)

    if most_bought_product is None:
        most_bought_product = get_most_bought_product_in_time(24)

    if most_bought_product is None:
        most_bought_product = {'product_amount': '', 'product_name': ''}

    return most_bought_product
