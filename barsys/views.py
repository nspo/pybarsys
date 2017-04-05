from django.shortcuts import render
from django.http import Http404
from django.shortcuts import get_list_or_404, get_object_or_404, redirect
from .models import Product, Category, User, Purchase
from .forms import SingleUserSinglePurchaseForm


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

    context = {"favorites": users, "all_users": users, "last_purchases": last_purchases}
    return render(request, 'barsys/user_list.html', context)
