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

   ```apt-get install libapache2-mod-wsgi-py3 apache2```
6. Create pybarsys apache2 config file (examples should work on Debian/Ubuntu and related Linux distributions):

   ```vim /etc/apache2/sites-available/pybarsys.conf```
   
   File contents (example):
   ```
   Alias /static/ /var/www/pybarsys/barsys/static/
   
   <Directory /var/www/pybarsys/barsys/static>
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
