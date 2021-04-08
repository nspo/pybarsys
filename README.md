# pybarsys
A beverage shopping system for bars of small private organizations - based on Django and Python 3.

Main developer: Nicolai Spohrer (nicolai[at]xeve.de)

# Features
* Easy installation with Docker and `docker-compose`
* Users can purchase products on their phone, tablet, or PC
* Responsive main and admin interface
* Handling of invoices and payments
* *Dependants* feature: dependant/friend accounts can be created for users which do not pay themselves, i.e. for which another user is responsible
* Semi-automatic mailing of
  * invoices
  * payment reminders
  * purchase notifications for dependants
* Customizable statistics (both in main and admin interface)
* *Happy hour* feature: change lots of product attributes (e.g. price or availability) in one step by creating a *Product Autochange Set*
* *Buy a round!* Users can choose to "donate" products so a specific amount of them are available for free
* *Pay your bills!* Users whose balance repeatedly falls below a threshold can be automatically locked from purchasing more until they clear their debts
* *MultiBuy!* When multiple people order the same thing, use the MultiBuy feature to save lots of time
* [REST API](docs/api.md) (by courtesy of [@jallmenroeder](https://github.com/jallmenroeder))
* ...
# Explanation & screenshots

![](/docs/pybarsys-principle.png)
All persons on the same network as the pybarsys server can purchase products with their tablet, phone, or PC.
Admins can log into a special admin interface with lots of features.

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
   * Login is needed for admin access of course
   * Don't make this available to the internet...

# Installation with Docker (recommended)
Pybarsys can be easily set up with Docker and `docker-compose`.
This is the recommended installation method.

## Initial installation

0. Install [Docker](https://docs.docker.com/engine/install/#server) and a current version of [`docker-compose`](https://docs.docker.com/compose/install/) on your server.
0. Choose where you want to put the database and configuration files of pybarsys. 
   Create an empty folder with an appropriate name:
   
   ```bash
   mkdir pybarsys
   cd pybarsys/
   ```
0. Use the automatic setup script to download the necessary configuration files:
   ```bash
   bash -c "$(curl -sSL "https://raw.githubusercontent.com/nspo/pybarsys/master/scripts/download_pybarsys_docker.sh" -o-)"
   ```
   Of course you can also download the script manually and review it before executing. 
   Root permissions are not needed for this step if your user has write permissions in the current folder.
0. Your system is ready to run pybarsys! Simply execute `sudo docker-compose up` to start pybarsys for the first time. 
0. You should be able to access the main page on `http://server_address` (e.g. `http://localhost` if you are running it locally).
   The admin interface can be accessed at `http://server_address/admin` with the default admin account `admin@example.com` (password: `example`).
   You should of course immediately change the password of the default admin account - alternatively you can create a new account with admin rights and delete the default account.
0. If everything seems fine so far, you can cancel the `docker-compose` command from the previous step with `CTRL+C` and start it again with the `-d` option to keep it running in the background:
   ```bash
   sudo docker-compose up -d
   ```
   This also makes sure that everything will be restarted automatically when you reboot the system.
0. [Configure pybarsys](docs/settings.md)! 
   There are some options which you will surely want to set if you use pybarsys in production, e.g. the mail server settings and language.
   To change a setting, simply edit the `.env` file as described in the link and restart pybarsys with `sudo docker-compose restart`.
   If you want to change the `nginx` configuration or adapt the `docker-compose.yml`, everything is available to be edited in the pybarsys folder.
   
## Apply pybarsys updates
First, backup your `.env` and `db.sqlite3` files so that you can always restore them.
You may also want to tag the current pybarsys image so you can more easily revert to it:

```bash
sudo docker tag nspohrer/pybarsys:latest nspohrer/pybarsys:pre-update
```

Check the pybarsys github page to see if any changes to your settings file may be necessary after the update.

`cd` to the folder where you set up pybarsys and update the pybarsys and nginx images:

```bash
sudo docker-compose stop
sudo docker-compose pull
sudo docker-compose up -d
```

Then check if everything still works fine! If you want to revert to your old state, stop the server, copy over your database backup, and revert to the older pybarsys image with `sudo docker tag nspohrer/pybarsys:pre-update nspohrer/pybarsys:latest`.

# Manual installation
In case you do not want to use the Docker installation method, e.g. because you want to change and debug the pybarsys code in your IDE or have other special requirements, pybarsys can of course also be installed manually.

## Initial installations

1. Download pybarsys into e.g. `/var/www/pybarsys` (you may need to create the parent folder first)
   ```bash
   # possibly: sudo mkdir /var/www
   cd /var/www
   sudo mkdir pybarsys && sudo chown $(whoami) pybarsys
   git clone https://github.com/nspo/pybarsys.git
   ```
1. Setup virtualenv and configuration (you may need to install `virtualenv` first)
   ```bash
   # Setup virtualenv and dependencies
   cd /var/www/pybarsys
   # possibly: sudo apt install virtualenv
   virtualenv -p python3 .
   source bin/activate # activate virtualenv
   pip3 install -r requirements.txt
   # Create .env configuration file and generate SECRET_KEY
   cat .env.example | grep -v "SECRET_KEY" > .env
   echo SECRET_KEY=$(tr -dc 'a-z0-9!@#%^&*(-_=+)' < /dev/urandom | head -c50) >> .env
   # Start a test server
   scripts/run_test_server.sh
   # CTRL+C to stop the server
   ```
1. If you just want to debug pybarsys, **you should be able to stop here**.
   Maybe you want to set some [debug settings](docs/settings.md) in your `.env` file.
   If you plan to run pybarsys in production, continue.
1. Think about [how to deploy Django](https://docs.djangoproject.com/en/2.2/howto/deployment/).
   Django is written in Python and does not include a real production webserver.
   Therefore, you should use something else (e.g. Apache2) to run a Django site.
   The example method we are going to use here is [apache2 with mod_wsgi](https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/modwsgi/)
1. Install apache2 (if not yet installed)

   ```bash
   sudo apt-get install libapache2-mod-wsgi-py3 apache2
   ```
1. Fix permissions (apache2 access needs r/w in pybarsys folder and `db.sqlite3`)
   ```bash
   sudo chown www-data.www-data .
   sudo chown www-data.www-data db.sqlite3
   ```

1. Create pybarsys apache2 config file (examples should work on Debian/Ubuntu and related Linux distributions):

   ```bash
   sudo nano /etc/apache2/sites-available/pybarsys.conf
   ```
   
   File contents (example):
   ```html
   WSGIDaemonProcess pybarsys python-home=/var/www/pybarsys python-path=/var/www/pybarsys home=/var/www/pybarsys
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
   
1. As with the Docker approach, you can [configure pybarsys-related settings](docs/settings.md) in your `.env` file.
   
1. Disable the apache2 default site that uses port 80, enable the pybarsys site and restart apache2:
   ```bash
   sudo a2dissite 000-default
   sudo a2ensite pybarsys
   sudo systemctl restart apache2
   ```

1. Login at `http://server_address/admin/` with the default admin account (`admin@example.com`, password `example`) to create more users, categories, products etc. and understand pybarsys!

## Apply pybarsys updates

First, backup everything:
```bash
sudo systemctl stop apache2
cd /var/www
sudo cp -a pybarsys /var/backups/$(date --iso-8601)-pybarsys
```

Make sure you have write permissions for *all* files in the pybarsys folder.
Basically, the following command should return nothing (except maybe a *few* static files under `.git`):

```bash
cd /var/www/pybarsys
find . -not -writable | grep -v ./lib
```

If you installed pybarsys with your current user you should be able to just add it to apache2's `www-data` group and change some file permissions slightly.
If you add your user to a new group, you need to close and reopen your shell.

```bash
sudo adduser $(whoami) www-data
sudo chmod g+w . db.sqlite3
# close and then reopen shell!
```

It is recommended to check the pybarsys github page for explanations of important changes.
You can also look into the git log:
```bash
git fetch # get information about changes but do not touch local files
git log origin/master # show latest changes on master
````

When you want to apply the update, simply pull in the changes (you should not have modified any pybarsys files):
```bash
git pull
```

It may be necessary to update the dependencies.
Also, start a test server (which will automatically migrate the database if necessary):
```bash
source bin/activate # activate virtual environment
pip3 install -r requirements.txt # update dependencies
scripts/run_test_server.sh
# If everything works fine, stop the test server with CTRL+C and restart apache2
sudo systemctl start apache2
```
If there are any issues you can try to fix them or in the worst case use your backup.

# Bug reports
Please feel free to open an issue in case you think you spotted a bug.
If you want to report a crash of pybarsys, don't forget to set `DEBUG=on` in your `.env` configuration file to get a more verbose error message.
