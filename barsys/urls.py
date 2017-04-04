from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.user_list, name="user_list"),
    url(r'^user/list/$', views.user_list, name="user_list"),

    url(r'^user/(?P<user_id>[0-9]+)/purchase/$', views.user_purchase, name='user_purchase'),
]
