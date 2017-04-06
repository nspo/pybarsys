from django.shortcuts import render
from django.http import Http404
from django.shortcuts import get_list_or_404, get_object_or_404, redirect
from .models import Product, Category, User, Purchase, StatsDisplay
from .forms import SingleUserSinglePurchaseForm
import datetime
from django.utils import timezone
from django.db import models
from collections import defaultdict


def user_purchase(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    categories = get_list_or_404(Category)

    if request.method == "POST":
        form = SingleUserSinglePurchaseForm(request.POST)

        if form.is_valid():
            user = User.objects.get(pk=form.cleaned_data["user_id"])
            product = Product.objects.get(pk=form.cleaned_data["product_id"])

            purchase = Purchase(user=user, product_name=product.name, product_amount=product.amount,
                                product_category=product.category.name, product_price=product.price,
                                quantity=form.cleaned_data["quantity"])
            purchase.save()
            return redirect(user_list)
        else:
            context = {"error_messages": ["Invalid form data"]}
    else:
        context = {}

    form = SingleUserSinglePurchaseForm()

    context["user"] = user
    context["categories"] = categories
    context["form"] = form

    return render(request, "barsys/user_purchase.html", context)


def user_list(request):
    users = get_list_or_404(User)
    try:
        last_purchases = Purchase.objects.order_by("-created_date")[:5]
    except Purchase.DoesNotExist:
        return Http404("Could not request last purchases")

    sidebar_stats_elements = StatsDisplay.get_renderable()

    context = {"favorites": users, "all_users": users, "last_purchases": last_purchases,
               "sidebar_stats_elements": sidebar_stats_elements}
    return render(request, 'barsys/user_list.html', context)


def user_history(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_active=True, is_buyer=True)
    midnight = datetime.time(0, 0, 0)
    prev_monday = timezone.now() - timezone.timedelta(days=timezone.now().weekday())
    midnight_prev_monday = datetime.datetime.combine(prev_monday, midnight)

    # Purchase quantity as list of dicts
    purchases_per_product = Purchase.objects.filter(user__pk=user_id,
                                                    created_date__gte=midnight_prev_monday
                                                    ).values("product_category", "product_name", "product_amount") \
        .annotate(total_quantity=models.Sum("quantity")).distinct()

    # Group product purchases by product_category
    categories = defaultdict(list)
    for prod in purchases_per_product:
        categories[prod["product_category"]].append(prod)

    categories = sorted(categories.items())

    context = {}
    context["user"] = user
    context["categories"] = categories
    return render(request, "barsys/user_history.html", context)
