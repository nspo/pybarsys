# pybarsys
A beverage shopping system for bars of small private organizations - based on Django and Python 3.

Developer: Nicolai Spohrer (nicolai[at]xeve.de)

# Features
* Responsive main interface and admin interface
* Products that are sorted into categories and can be purchased by all users in the main interface (e.g. on a tablet, phones or PCs)
* Detailed information about every purchase
* Creation of invoices for unbilled purchases
* Management of users ("dependants"/"friends") who do not pay themselves, but for whose purchases some other user is responsible
* Automatical mailing of 
  * invoices
  * payment reminders
  * purchase notifications for dependants
* Management of payments from and to user accounts
* Configurable statistical displays on main page
* Statistics in admin interface
* Automatical changes of product attributes: set "happy hour prices" etc. once by creating a `product autochange set` and apply them with one single click
* Free items
  * Users can choose to "donate" products to all other users so that they can be purchased for no cost
  * Useful for birthday events etc.
# Explanation & screenshots

![](/docs/pybarsys-principle.png)
Persons who are in the same computer network can access the pybarsys main interace (this could be changed with custom settings). Admins have to provide their email address and password to access the administration area.

Screenshots | Screenshots | Screenshots 
------------|-------------|------------
Main page|Purchasing as a single user|Purchasing and "donating"
![](/docs/screenshots/screenshot-1.png)|![](/docs/screenshots/screenshot-2.png)|![](/docs/screenshots/screenshot-3.png)
Purchasing with free items|Admin: free items|Admin: invoice details on phone (responsive)
![](/docs/screenshots/screenshot-17.png)|![](/docs/screenshots/screenshot-16.png)|![](/docs/screenshots/screenshot-21.png)
User history 1|User history 2|MultiBuy step 1: Buying as multiple users at once
![](/docs/screenshots/screenshot-4.png)|![](/docs/screenshots/screenshot-5.png)|![](/docs/screenshots/screenshot-6.png)
MultiBuy step 2|Admin: purchase list|Admin: payment list
![](/docs/screenshots/screenshot-7.png)|![](/docs/screenshots/screenshot-8.png)|![](/docs/screenshots/screenshot-9.png)
Admin: created invoices|Admin: updating stats display|Admin: updating product autochange set
![](/docs/screenshots/screenshot-10.png)|![](/docs/screenshots/screenshot-11.png)|![](/docs/screenshots/screenshot-12.png)
Admin: applied product autochange set|Purchase statistics 1|Purchase statistics 2
![](/docs/screenshots/screenshot-13.png)|![](/docs/screenshots/screenshot-14.png)|![](/docs/screenshots/screenshot-15.png)
Main interface on phone|Invoice mail|Invoice mail: purchases of a dependant
![](/docs/screenshots/screenshot-18.png)|![](/docs/screenshots/screenshot-19.png)|![](/docs/screenshots/screenshot-20.png)

# Installation
1. Download pybarsys into e.g. /var/www/pybarsys
2. Setup virtualenv
   ```bash
   cd /var/www/
   virtualenv -p python3 pybarsys
   cd pybarsys
   source bin/activate # activate virtualenv
   pip3 install -r requirements.txt
   # Create database
   python3 manage.py migrate
   # Optional: test with builtin server
   python3 manage.py runserver 0.0.0.0:4000 --insecure
   # CTRL+C
   ```
3. Think about [how to deploy Django](https://docs.djangoproject.com/en/1.11/howto/deployment/)
4. Easiest/example method to deploy: [apache2 with mod_wsgi](https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/modwsgi/)
5. Install apache2 (if not yet installed)

   ```bash
   sudo apt-get install libapache2-mod-wsgi-py3 apache2
   ```
6. Fix permissions (database access needs r/w in pybarsys folder and db.sqlite3)
   ```bash
   sudo chown www-data .
   sudo chown www-data db.sqlite3
   ```
7. Create pybarsys apache2 config file (examples should work on Debian/Ubuntu and related Linux distributions):

   ```bash
   sudo vim /etc/apache2/sites-available/pybarsys.conf
   ```
   
   File contents (example):
   ```html
   Alias /static/admin/ /var/www/pybarsys/lib/python3.5/site-packages/django/contrib/admin/static/admin/

   <Directory /static/admin>
   Require all granted
   </Directory>


   Alias /static/ /var/www/pybarsys/barsys/static/

   <Directory /static>
   Require all granted
   </Directory>


   WSGIScriptAlias / /var/www/pybarsys/pybarsys/wsgi.py
   WSGIPythonHome /var/www/pybarsys
   WSGIPythonPath /var/www/pybarsys

   <Directory /var/www/pybarsys/pybarsys>
   <Files wsgi.py>
   Require all granted
   </Files>
   </Directory>
   ```
8. Reload apache2
   ```sudo service apache2 reload```
   
9. Change pybarsys/settings.py: switch to production settings file
10. Change pybarsys/_settings/production.py:
   * Set own `SECRET_KEY`
   * Set `LANGUAGE_CODE` (e.g. `"de-de"` for German)
   * Change mail settings (`EMAIL_HOST` etc.) to be able to send invoices
   * ...
   
11. Create superuser
   ```python
   /v/w/pybarsys> sudo python3 manage.py shell
   from barsys.models import *
   u=User.objects.create_superuser(email="admin@example.com", password="example", display_name="Admin")
   u.is_buyer = False
   u.save()
   u2=User.objects.create(email="jessica@example.com", display_name="Jessica")
   ```
12. Login at http://localhost/admin/ and create other users, categories, products, ...
13. Change other settings like bank account details at `Misc -> External admin interface (settings)`
14. Adapt mail templates under barsys/templates/email/ to your own preferences

# Bug reports
Please feel free to open an issue in case you think you spotted a bug.

# Donations
In case you want to donate something to me for pybarsys, here's a paypal link: [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://paypal.me/NSpohrer)
