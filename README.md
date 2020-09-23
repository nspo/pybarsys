# pybarsys
A beverage shopping system for bars of small private organizations - based on Django and Python 3.

Main developer: Nicolai Spohrer (nicolai[at]xeve.de)

# Features
* Responsive main and admin interface
* Products that are sorted into categories and can be purchased by all users in the main interface (e.g. on a tablet, phones or PCs)
* Detailed information about every purchase
* Creation of invoices for unbilled purchases and payments
* Management of users who do not pay themselves ("dependants"/"friends"), but for whose purchases some other user is responsible
* Semi-automatical mailing of 
  * invoices
  * payment reminders
  * purchase notifications for dependants
* Management of payments from and to user accounts
* Configurable statistical displays on main page
* Statistics in admin interface
* Semi-automatical changes of product attributes: set "happy hour prices" etc. once by creating a `product autochange set` and apply them with one single click
* Free items
  * Users can choose to "donate" products to all other users so that they can be purchased for no cost
  * Useful for birthday events etc.
* Users can be "autolocked" if their balance falls below a threshold two times in a row
* [REST API](/docs/api.md) (by courtesy of [@jallmenroeder](https://github.com/jallmenroeder))
* ...
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

# Limitations
 * German and Dutch (thanks [@Merlijnv](https://github.com/Merlijnv)) translations are available for the mail templates, but not for the main and admin interface
 * Based on the assumption that everyone with access to the main page may purchase products for all active users
   * You should run the server in a trusted local area network
   * Login needed for admin access of course
   * Don't make this available to the internet...
 * [...]
# Installation
1. Download pybarsys into e.g. `/var/www/pybarsys`
   ```bash
   cd /var/www
   git clone https://github.com/nspo/pybarsys.git
   ```
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
   # CTRL+
   ```
3. Think about [how to deploy Django](https://docs.djangoproject.com/en/1.11/howto/deployment/): Django is written in Python and does not include a real webserver. Therefore you need something else (e.g. Apache2) to run a Django site.
4. Easiest/example method to deploy: [apache2 with mod_wsgi](https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/modwsgi/)
5. Install apache2 (if not yet installed)

   ```bash
   sudo apt-get install libapache2-mod-wsgi-py3 apache2
   ```
6. Fix permissions (database access needs r/w in pybarsys folder and `db.sqlite3`)
   ```bash
   sudo chown www-data .
   sudo chown www-data db.sqlite3
   ```
   Alternative, more drastic version if apache2 later complains about not having permissions:
   ```bash
   sudo chown www-data -R .
   ```
7. Create pybarsys apache2 config file (examples should work on Debian/Ubuntu and related Linux distributions):

   ```bash
   sudo nano /etc/apache2/sites-available/pybarsys.conf
   ```
   
   File contents (example):
   ```html
    WSGIDaemonProcess pybarsys python-home=/var/www/pybarsys python-path=/var/www/pybarsys
    WSGIProcessGroup pybarsys

    <VirtualHost *:80>
        Alias /static/ /var/www/pybarsys/barsys/static/
        <Directory /static>
            Require all granted
        </Directory>
        WSGIScriptAlias / /var/www/pybarsys/pybarsys/wsgi.py process-group=pybarsys
        <Directory /var/www/pybarsys/pybarsys>
            <Files wsgi.py>
                Require all granted
            </Files>
        </Directory>
    </VirtualHost>
   ```
8. Disable apache2 default site that uses port 80, enable pybarsys site and restart apache2
   ```bash
   sudo a2dissite 000-default
   sudo a2ensite pybarsys
   sudo systemctl restart apache2
   ```
   
9. Copy `pybarsys/_settings/production.py` to `pybarsys/_settings/production_yourbar.py` and set your own settings:
   ```bash
   cd /var/www/pybarsys/pybarsys/_settings
   cp production.py production_yourbar.py
   nano production_yourbar.py
   ```
   * Set own `SECRET_KEY`
   * Set `LANGUAGE_CODE` (e.g. `"de-de"` for German, `"nl-NL"` or `"en-US"`)
     * Note that the LANGUAGE_CODE currently has to have the form "ab-CD" with a dash in the middle
     * You can also switch to the German or Dutch mail templates (with PybarsysPreferences)
   * Change mail settings (`EMAIL_HOST` etc.) to be able to send invoices
   * Set PybarsysPreferences (have a look at `common.py` to see all options)
   * Set own STATIC_URL if needed
   * If you want the minus sign in front of your value and valuta but changing the locale doesn't fix this then you can set NEGATIVE_FIRST to True and change the VALUTASIGN to your own currency sign in your production_yourbar.
   * ...
   * This copy is necessary to have a clear differentiation between your custom config and the pybarsys default files. Otherwise, your configuration might accidentally be overwritten when you download a pybarsys update.
   
10. Change `pybarsys/settings.py`: comment out dev settings and uncomment the line with `production_yourbar` so that the `pybarsys/_settings/production_yourbar.py` settings file is used
   
11. Reload Apache2 to use new settings:
   ```sudo systemctl reload apache2```
12. Create pybarsys superuser
   ```python
   /var/www/pybarsys> sudo python3 manage.py shell
   from barsys.models import *
   u=User.objects.create_superuser(email="admin@example.com", password="example", display_name="Admin")
   u.is_buyer = False
   u.save()
   u2=User.objects.create(email="jessica@example.com", display_name="Jessica")
   ```
13. Login at http://your_server_ip/admin/ to create more users, categories, products etc. and understand pybarsys

# How to update pybarsys?
```bash
sudo systemctl stop apache2
cd /var/www
sudo cp -a pybarsys /var/backups/2000-01-01-pybarsys # backup!
cd pybarsys
git diff # see what files you have changed
```
You should *only* have changed `pybarsys/settings.py` to reference your own `production_yourbar` settings.
If that is the case, proceed as follows. Otherwise, change everything back to the pybarsys default except `python/settings.py` or at least be careful what you do.

Make sure you have write permissions for pybarsys. In this example the current user `it` is in the group assigned to pybarsys but has no write permissions. If you want to set the group of all files to `it` first, you could do `sudo chgrp it -R .`.
```bash
sudo chmod g+rw -R . # allow reading/writing to all files in current folder for group
git stash # stash changes to python/settings.py
git pull # get pybarsys update
git stash pop # pop stashed changes from above

source bin/activate # activate virtual environment
pip3 install -r requirements.txt # update dependencies
python3 manage.py migrate # update database
sudo systemctl start apache2
```
Finally, test whether everything works again. If not, you can try to fix the error or use your backup.

# Troubleshooting

It shouldn't be necessary when running pip3 install with sudo if it gives errors then change the folder permission with:
'''
cd /var/www/
chmod +rwx pybarsys
'''


# Bug reports
Please feel free to open an issue in case you think you spotted a bug.
