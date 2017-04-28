"""pybarsys URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth import views as auth_views

from barsys.forms import LoginForm

urlpatterns = [
    url(r'^django-admin/', admin.site.urls),
    url(r'^', include('barsys.urls')),

    # user area
    url(r'^login/$', auth_views.LoginView.as_view(),
        {'template_name': 'barsys/admin/login.html', 'authentication_form': LoginForm},
        name="user_login"),
    url(r'^logout/$', auth_views.logout, {'next_page': 'user_login'}, name="user_logout"),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^debug/', include(debug_toolbar.urls)),
    ] + urlpatterns
