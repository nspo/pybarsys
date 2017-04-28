# pybarsys
A beverage shopping system for bars of small private organizations

# Features
* Responsive main interface and admin interface
* Products that are sorted into categories and can be purchased by all users in the main interface (e.g. on a tablet, phones or PCs)
* Detailed information about every purchase
* Creation of invoices for unbilled purchases
* Creation of users (dependants/"friends") who do not pay themselves, but for whose purchases some other user is responsible
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
   python3 manage.py runserver
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
   
9. Change pybarsys/settings.py
   * Set own `SECRET_KEY`
   * Make sure `DEBUG=False`
   * Set `LANGUAGE_CODE` (e.g. `"de-de"` for German)
   * Change mail settings (`EMAIL_HOST` etc.) to be able to send invoices
   * ...
   
10. Create superuser
   ```python
   /v/w/pybarsys> sudo python3 manage.py shell
   from barsys.models import *
   u=User.objects.create_superuser(email="admin@example.com", password="example", display_name="Admin")
   ```
11. Login at http://localhost/admin/ and create other users, categories, products, ...
12. Change other settings like bank account details at `Misc -> External admin interface (settings)`
13. Adapt mail templates under barsys/templates/email/ to your own preferences

# Bug reports
Please feel free to open an issue in case you think you spotted a bug.

# Donations and technical support
In case you want to donate something to me for pybarsys, here's a paypal link: [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://paypal.me/NSpohrer)

Should you want to receive paid technical support or pay for the addition of new features, you can contact me at nicolai[at]xeve.de.
