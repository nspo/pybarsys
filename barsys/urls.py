from django.conf.urls import url

from . import views, filters

urlpatterns = [
    # main page for purchasing products (main_*)
    url(r'^$', views.main_user_list, name="root"),
    url(r'^user/list/$', views.main_user_list, name="main_user_list"),
    url(r'^user/(?P<user_id>[0-9]+)/purchase/$', views.main_user_purchase, name='main_user_purchase'),
    url(r'^user/(?P<user_id>[0-9]+)/history/$', views.main_user_history, name='main_user_history'),

    # user area (user_*)
    url(r'^userarea/$', views.user_home, name='user_home'),

    # Purchase
    url(r'^userarea/purchase/$',     views.PurchaseListView.as_view(), name="user_purchase_list"),
    url(r'^userarea/purchase/new/$', views.PurchaseCreateView.as_view(), name='user_purchase_new'),
    url(r'^userarea/purchase/(?P<pk>[0-9]+)/detail/$', views.PurchaseDetailView.as_view(), name='user_purchase_detail'),
    url(r'^userarea/purchase/(?P<pk>[0-9]+)/update/$', views.PurchaseUpdateView.as_view(), name='user_purchase_update'),
    url(r'^userarea/purchase/(?P<pk>[0-9]+)/delete/$', views.PurchaseDeleteView.as_view(), name='user_purchase_delete'),

    # User
    url(r'^userarea/user/$', views.UserListView.as_view(), name='user_user_list'),
    url(r'^userarea/user/new/$', views.UserCreateView.as_view(), name='user_user_new'),
    url(r'^userarea/user/(?P<pk>[0-9]+)/detail/$', views.UserDetailView.as_view(), name='user_user_detail'),
    url(r'^userarea/user/(?P<pk>[0-9]+)/update/$', views.UserUpdateView.as_view(), name='user_user_update'),
    url(r'^userarea/user/(?P<pk>[0-9]+)/delete/$', views.UserDeleteView.as_view(), name='user_user_delete'),
]
