# pybarsys
A beverage shopping system for bars of small private organizations

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
3. Think about how to deploy Django: https://docs.djangoproject.com/en/1.11/howto/deployment/
4. Easiest/example method to deploy: apache2 with mod_wsgi (https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/modwsgi/)
5. Install apache2 (if not yet installed)

   ```sudo apt-get install libapache2-mod-wsgi-py3 apache2```
6. Fix permissions (database access needs r/w in pybarsys folder and db.sqlite3)
   ```
   sudo chown www-data .
   sudo chown www-data db.sqlite3
   ```
7. Create pybarsys apache2 config file (examples should work on Debian/Ubuntu and related Linux distributions):

   ```sudo vim /etc/apache2/sites-available/pybarsys.conf```
   
   File contents (example):
   ```
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
   ```/v/w/pybarsys> sudo python3 manage.py shell
   from barsys.models import *
   u=User.objects.create_superuser(email="admin@example.com", password="example", display_name="Admin")
   ```
11. Login at http://localhost/admin/ and create other users, categories, products, ...
12. Change other settings like bank account details at `Misc -> External admin interface (settings)`
13. Adapt mail templates under barsys/templates/email/ to your own preferences
