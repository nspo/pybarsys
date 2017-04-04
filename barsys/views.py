from django.shortcuts import render
from django.shortcuts import get_list_or_404, get_object_or_404
from .models import Product, Category, User

def user_purchase(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    categories = get_list_or_404(Category)
    context = {"user" : user, "categories" : categories}
    return render(request, "barsys/user_purchase.html", context)

def user_list(request):
    users = get_list_or_404(User)

    context = {"favorites" : users, "all_users" : users}
    return render(request, 'barsys/user_list.html', context)