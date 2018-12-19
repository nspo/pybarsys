from .common import *
# Put your production settings in this file!

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '&_cx6qdzz^1w%per*z6emn$*&937j-^0@q93g+t9fk7hy%8p(%'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ["127.0.0.1", "192.168.0.133", "localhost", ]

# Email settings
EMAIL_HOST = 'localhost'
# EMAIL_HOST_USER = 'no-reply@example.com'
# EMAIL_HOST_PASSWORD = 'hunter2'
EMAIL_FROM_ADDRESS = 'no-reply@example.com'
EMAIL_PORT = 1025  # 587
EMAIL_USE_TLS = False  # True

# Put the preferences you want to change here
# PybarsysPreferences.EMAIL.CONTACT_EMAIL = "bar@ieee.org"
# PybarsysPreferences.EMAIL.TEMPLATE_DIR = "email_german"
# PybarsysPreferences.EMAIL.BANK_ACCOUNT_RECIPIENT = "Foo-Bank"
# PybarsysPreferences.EMAIL.INVOICE_SUBJECT = "Barrechnung von der Foo-Bar"
# ...
