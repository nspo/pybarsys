import os.path
from collections import OrderedDict
from itertools import groupby
from typing import Iterable, Optional

from django.contrib import messages
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone

from pybarsys import settings as pybarsys_settings
from pybarsys.settings import PybarsysPreferences
from .models import StatsDisplay, Purchase, Invoice, Product, User


def get_renderable_stats_elements():
    """Create a list of dicts for all StatsDisplays that can be rendered by view more easily"""
    stats_elements = []

    all_displays = StatsDisplay.objects.prefetch_related(
        "filter_by_category", "filter_by_product"
    ).order_by("-show_by_default")
    if PybarsysPreferences.Misc.SHUFFLE_STATSDISPLAY_ORDER:
        all_displays = all_displays.order_by("?")

    for index, stat in enumerate(all_displays):
        stats_element = {
            "stats_id": "stats_{}".format(stat.pk),
            "show_by_default": stat.show_by_default,
            "title": stat.title,
        }

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
            filters["product_category__in"] = [
                c["name"] for c in stat.filter_by_category.values("name")
            ]

        if stat.filter_by_product.all().exists():
            filters["product_name__in"] = [
                p["name"] for p in stat.filter_by_product.values("name")
            ]

        # filter by time
        filters["created_date__gte"] = stat.time_period_begin()

        stats_element["rows"] = []
        if stat.sort_by_and_show == StatsDisplay.SORT_BY_NUM_PURCHASES:
            top_users = Purchase.objects.filter(**filters).stats_purchases_by_user(
                limit=PybarsysPreferences.Misc.NUM_MAIN_USERS_IN_STATSDISPLAY
            )
            for user_id, user_name, total_quantity in top_users:
                stats_element["rows"].append(
                    {
                        "left": "{}x".format(total_quantity),
                        "row_string": stat.row_string,
                        "user_name": user_name,
                        "user_id": user_id,
                    }
                )
        else:
            top_users = Purchase.objects.filter(**filters).stats_cost_by_user(
                limit=PybarsysPreferences.Misc.NUM_MAIN_USERS_IN_STATSDISPLAY
            )
            for u_index, (user_id, user_name, total_cost) in enumerate(top_users):
                stats_element["rows"].append(
                    {
                        "left": "{}.".format(u_index + 1),
                        "row_string": stat.row_string,
                        "user_name": user_name,
                        "user_id": user_id,
                    }
                )

        if index + 1 < len(all_displays):
            # toggle next one on
            stats_element["toggle_other_on"] = "stats_{}".format(
                all_displays[index + 1].pk
            )
        else:
            # toggle first one on
            stats_element["toggle_other_on"] = "stats_{}".format(all_displays[0].pk)
        # if there is only one display, it's toggled off and on again with one click

        stats_elements.append(stats_element)

    return stats_elements


class EmailConnectionWrapper:
    """Wraps a Django mail connection with error-safe bool-returning send_message().

    This can also be used to simulate sending a mail when that may not be wanted due to preferences.
    """

    def __init__(self, fake_sending_mails: bool) -> None:
        """Open the mail connection. Raises on connection failure.

        Args:
            fake_sending_mails: If True, simulate success without actually sending any mail.
        """
        self.fake_sending_mails = fake_sending_mails
        self.last_error: Optional[Exception] = None
        self.error_count: int = 0  # incremented on each failed send_message() call
        self._connection = None
        if not fake_sending_mails:
            self._connection = mail.get_connection(fail_silently=False)
            self._connection.open()  # may raise

    def send_message(self, msg: EmailMultiAlternatives) -> bool:
        """Send a single message. Returns True on success, False on failure.

        Note: Django's send_messages() returns an int (number of messages sent);
        this wrapper returns bool instead.
        """
        if self.fake_sending_mails:
            return True
        try:
            self._connection.send_messages((msg,))
            return True
        except Exception as e:
            self.last_error = e
            self.error_count += 1
            return False

    def close(self) -> None:
        """Close the mail connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __del__(self) -> None:
        self.close()


def generate_email_invoice(invoice: Invoice) -> EmailMultiAlternatives:
    """Generate invoice mail for a normal, paying user."""
    context = {}
    context["pybarsys_preferences"] = PybarsysPreferences
    context["subject"] = PybarsysPreferences.EMAIL.INVOICE_SUBJECT
    context["invoice"] = invoice
    context["recipient"] = invoice.recipient
    context["own_purchases"] = invoice.own_purchases()
    context["other_purchases_grouped"] = invoice.other_purchases_grouped()
    context["last_invoices"] = invoice.recipient.invoices()[:5]
    context["payments"] = invoice.payments()

    content_plain = render_to_string(
        os.path.join(
            PybarsysPreferences.EMAIL.TEMPLATE_DIR, "normal_invoice.plaintext.html"
        ),
        context,
    )
    content_html = render_to_string(
        os.path.join(
            PybarsysPreferences.EMAIL.TEMPLATE_DIR, "normal_invoice.html.html"
        ),
        context,
    )
    msg = EmailMultiAlternatives(
        PybarsysPreferences.EMAIL.INVOICE_SUBJECT,
        content_plain,
        pybarsys_settings.EMAIL_FROM_ADDRESS,
        [invoice.recipient.email],
        reply_to=[PybarsysPreferences.EMAIL.CONTACT_EMAIL],
    )
    msg.attach_alternative(content_html, "text/html")

    return msg


def generate_email_purchase_notification(
    dependant: User, purchases: Iterable[Purchase], invoice: Invoice
) -> EmailMultiAlternatives:
    """Generate purchase notification mail for a dependant."""
    notif_context = {}
    notif_context["pybarsys_preferences"] = PybarsysPreferences
    notif_context["subject"] = PybarsysPreferences.EMAIL.PURCHASE_NOTIFICATION_SUBJECT
    notif_context["invoice"] = invoice
    notif_context["dependant"] = dependant
    notif_context["purchases"] = purchases
    content_plain = render_to_string(
        os.path.join(
            PybarsysPreferences.EMAIL.TEMPLATE_DIR,
            "dependant_notification.plaintext.html",
        ),
        notif_context,
    )
    content_html = render_to_string(
        os.path.join(
            PybarsysPreferences.EMAIL.TEMPLATE_DIR, "dependant_notification.html.html"
        ),
        notif_context,
    )
    msg = EmailMultiAlternatives(
        PybarsysPreferences.EMAIL.PURCHASE_NOTIFICATION_SUBJECT,
        content_plain,
        pybarsys_settings.EMAIL_FROM_ADDRESS,
        [dependant.email],
        reply_to=[PybarsysPreferences.EMAIL.CONTACT_EMAIL],
    )
    msg.attach_alternative(content_html, "text/html")

    return msg


def create_invoices(
    request,
    users: list[User],
    send_mails: bool,
    send_dependant_notifications: bool,
    send_payment_reminders: bool,
    autolock_accounts: bool,
    comment: str = "",
) -> list[Invoice]:
    """Create invoices for users, send mails, handle autolocking. Returns list of created Invoice objects."""
    invoices = []
    users_autolocked: list[User] = []
    users_autounlocked: list[User] = []

    # Only send these if we also want to send mails at all
    send_dependant_notifications = send_mails and send_dependant_notifications
    send_payment_reminders = send_mails and send_payment_reminders

    num_invoice_mail_success = 0
    invoice_mail_failure: list[tuple[User, Exception]] = []

    num_reminder_mail_success = 0
    reminder_mail_failure: list[tuple[User, Exception]] = []

    # for dependants
    num_purchase_notif_mail_success = 0
    purchase_notif_mail_failure: list[tuple[User, Exception]] = []

    # open connection only once to avoid repeated unnecessary connections for multiple mails
    # fake opening the connection if we do not want to send any emails (to keep the logic the same as when we do)
    try:
        conn = EmailConnectionWrapper(fake_sending_mails=not send_mails)
    except Exception as e:
        messages.error(
            request,
            "No invoice(s) created because connection to mail server could not be "
            "established: {}".format(e),
        )
        return invoices

    MAIL_CONNECTION_FAILURE_COUNT_LIMIT = 4

    for user in users:
        if conn.error_count >= MAIL_CONNECTION_FAILURE_COUNT_LIMIT:
            messages.error(
                request,
                "Too many errors during mail transmission - "
                "stopped invoice creation process early",
            )
            break

        balance_before = user.account_balance()

        if (
            Purchase.objects.to_pay_by(user).exists()
            or user.payments().unbilled().exists()
        ):
            # create and send invoice
            invoice = Invoice.objects.create_for_user(user, comment)
            if conn.send_message(generate_email_invoice(invoice)):
                num_invoice_mail_success += 1
                invoices.append(invoice)

                # check whether dependants need to get purchase notifications
                if send_dependant_notifications and invoice.has_dependant_purchases():
                    # send purchase notifications to dependants
                    for dependant, purchases in invoice.other_purchases_grouped():
                        if conn.send_message(
                            generate_email_purchase_notification(
                                dependant, purchases, invoice
                            )
                        ):
                            num_purchase_notif_mail_success += 1
                        else:
                            purchase_notif_mail_failure.append(
                                (dependant, conn.last_error)
                            )
                            # do not delete invoice due to this, but count as error
            else:
                invoice_mail_failure.append((invoice.recipient, conn.last_error))
                invoice.delete()  # do not locally create an invoice if mail tx failed
                continue
        else:
            # no new invoice needed -> check whether payment reminder is needed
            if (
                send_payment_reminders
                and user.account_balance()
                < PybarsysPreferences.Misc.BALANCE_BELOW_TRANSFER_MONEY
            ):
                # send payment reminder
                if conn.send_message(generate_email_payment_reminder(user)):
                    num_reminder_mail_success += 1
                else:
                    reminder_mail_failure.append((user, conn.last_error))

        if (
            user.is_autolocked
            and user.account_balance() > PybarsysPreferences.Misc.BALANCE_BELOW_AUTOLOCK
        ):
            user.is_autolocked = False
            user.save()
            users_autounlocked.append(user)

        if autolock_accounts and not user.is_autolocked:
            if (
                balance_before < PybarsysPreferences.Misc.BALANCE_BELOW_AUTOLOCK
                and user.account_balance()
                < PybarsysPreferences.Misc.BALANCE_BELOW_AUTOLOCK
            ):
                # autolock is needed
                user.is_autolocked = True
                user.save()
                users_autolocked.append(user)

    if len(invoices) > 0:
        messages.success(
            request,
            "Created {} invoice(s) for: {}.".format(
                len(invoices), ", ".join([i.recipient.display_name for i in invoices])
            ),
        )
    else:
        messages.info(request, "No invoices were created.")

    if len(users_autolocked) > 0:
        messages.warning(
            request,
            "The following users were autolocked: {}".format(
                ", ".join([str(u) for u in users_autolocked])
            ),
        )

    if len(users_autounlocked) > 0:
        messages.success(
            request,
            "The following users were auto-unlocked: {}".format(
                ", ".join([str(u) for u in users_autounlocked])
            ),
        )

    if send_mails:
        if num_invoice_mail_success > 0:
            messages.info(request, f"Sent {num_invoice_mail_success} invoice mails")
        if len(invoice_mail_failure) > 0:
            messages.error(
                request,
                "Sending invoice mail(s) to the following user(s) failed - no invoices were created: {}".format(
                    ", ".join(
                        ["{} ({})".format(u, err) for u, err in invoice_mail_failure]
                    )
                ),
            )

    if send_dependant_notifications:
        if num_purchase_notif_mail_success > 0:
            messages.info(
                request,
                "{} dependant notification mails were successfully sent. ".format(
                    num_purchase_notif_mail_success
                ),
            )
        if len(purchase_notif_mail_failure) > 0:
            messages.error(
                request,
                "Sending dependant notification mail(s) to the following user(s) failed: {}".format(
                    ", ".join(
                        [
                            "{} ({})".format(u, err)
                            for u, err in purchase_notif_mail_failure
                        ]
                    )
                ),
            )

    if send_payment_reminders:
        if num_reminder_mail_success > 0:
            messages.info(
                request,
                "{} payment reminders were successfully sent. ".format(
                    num_reminder_mail_success
                ),
            )
        if len(reminder_mail_failure) > 0:
            messages.error(
                request,
                "Sending payment reminder mail(s) to the following user(s) failed: {}".format(
                    ", ".join(
                        ["{} ({})".format(u, err) for u, err in reminder_mail_failure]
                    )
                ),
            )

    conn.close()

    return invoices


def generate_email_payment_reminder(user: User) -> EmailMultiAlternatives:
    """Generate an email to be sent to a normal, paying user who does not have a new invoice"""
    context = {}
    context["pybarsys_preferences"] = PybarsysPreferences
    context["subject"] = PybarsysPreferences.EMAIL.PAYMENT_REMINDER_SUBJECT
    context["user"] = user
    context["recipient"] = user
    context["last_invoices"] = user.invoices()[:5]
    context["last_payments"] = user.payments()[:5]
    content_plain = render_to_string(
        os.path.join(
            PybarsysPreferences.EMAIL.TEMPLATE_DIR, "payment_reminder.plaintext.html"
        ),
        context,
    )
    content_html = render_to_string(
        os.path.join(
            PybarsysPreferences.EMAIL.TEMPLATE_DIR, "payment_reminder.html.html"
        ),
        context,
    )
    msg = EmailMultiAlternatives(
        PybarsysPreferences.EMAIL.PAYMENT_REMINDER_SUBJECT,
        content_plain,
        pybarsys_settings.EMAIL_FROM_ADDRESS,
        [user.email],
        reply_to=[PybarsysPreferences.EMAIL.CONTACT_EMAIL],
    )
    msg.attach_alternative(content_html, "text/html")

    return msg


def group_users(ungrouped_users):
    """Group users by first letter of name"""
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
    letter_group["A B C"] = ["A", "B", "C"]
    letter_group["D E F"] = ["D", "E", "F"]
    letter_group["G H I"] = ["G", "H", "I"]
    letter_groups_by_line.append(letter_group)

    letter_group = OrderedDict()
    letter_group["J K L"] = ["J", "K", "L"]
    letter_group["M N O"] = ["M", "N", "O"]
    letter_groups_by_line.append(letter_group)

    letter_group = OrderedDict()
    letter_group["P Q R S"] = ["P", "Q", "R", "S"]
    letter_group["T U V"] = ["T", "U", "V"]
    letter_group["W X Y Z"] = ["W", "X", "Y", "Z"]
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

    most_bought_products = (
        purchase_query_set.values("product_name", "product_amount")
        .order_by()
        .annotate(
            models.Count("product_name"), num_purchases=models.Count("product_amount")
        )
        .order_by("-num_purchases")
    )
    for prod in most_bought_products:
        if (
            Product.objects.active()
            .filter(name=prod["product_name"], amount=prod["product_amount"])
            .exists()
        ):
            return prod
            # else continue
    return None  # None found or None still available


def get_most_bought_product_in_time(hours):
    return get_most_bought_product_in_queryset(
        Purchase.objects.filter(
            created_date__gte=timezone.now() - timezone.timedelta(hours=hours)
        )
    )


def get_most_bought_product_for_user(user):
    most_bought_product = None
    if user.purchases().unbilled().exists():
        # most bought product of unbilled purchases
        most_bought_product = get_most_bought_product_in_queryset(
            user.purchases().unbilled()
        )

    if (
        most_bought_product is None
        and Invoice.objects.filter(purchase__user=user).distinct().exists()
    ):
        # most bought product by this user on last invoice that had a purchase of him/her
        # works both when user pays themselves and when not
        most_bought_product = get_most_bought_product_in_queryset(
            Invoice.objects.filter(purchase__user=user)
            .distinct()[0]
            .purchases()
            .filter(user=user)
        )

    if most_bought_product is None:
        # user has no purchases yet, just use all purchases of last 4 hours
        most_bought_product = get_most_bought_product_in_time(hours=4)

    if most_bought_product is None:
        # okay, so maybe last 24 hours?
        most_bought_product = get_most_bought_product_in_time(hours=24)

    if most_bought_product is None:
        # Found none :(
        most_bought_product = {"product_amount": "", "product_name": ""}

    return most_bought_product


def get_most_bought_product_for_users(users):
    most_bought_product = None
    if users.purchases().unbilled().exists():
        # most bought product of unbilled purchases
        most_bought_product = get_most_bought_product_in_queryset(
            users.purchases().unbilled()
        )

    if most_bought_product is None:
        # Show most bought product of last 4 hours
        most_bought_product = get_most_bought_product_in_time(4)

    if most_bought_product is None:
        most_bought_product = get_most_bought_product_in_time(24)

    if most_bought_product is None:
        most_bought_product = {"product_amount": "", "product_name": ""}

    return most_bought_product
