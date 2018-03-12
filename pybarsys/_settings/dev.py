from .common import *

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '&_cx6qdzz^1w%per*z6emn$*&937j-^0@q93g+t9fk7hy%8p(%'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost", ]

TEMPLATES[0]["OPTIONS"]["string_if_invalid"] = "!INVALID!"

INSTALLED_APPS.append('debug_toolbar')

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda e: False,
    'DISABLE_PANELS': {
        'debug_toolbar.panels.redirects.RedirectsPanel',
        'debug_toolbar.panels.templates.TemplatesPanel'
    },
}

DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.logging.LoggingPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
    'debug_toolbar.panels.profiling.ProfilingPanel',
]

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
