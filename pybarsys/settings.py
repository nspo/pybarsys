import os
from decimal import Decimal
import environ # https://django-environ.readthedocs.io/en/latest/

env = environ.Env()
env.read_env(".env")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__ + "/..")))
STATIC_ROOT = env("STATIC_ROOT", default="static/")
STATIC_URL = env("STATIC_URL", default="/static/")
SESSION_COOKIE_NAME = env("SESSION_COOKIE_NAME", default="pybarsys")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'bootstrap3',
    'barsys.apps.BarsysConfig',
    'django_filters',
    'crispy_forms',
    'rest_framework',
]

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'pybarsys.urls'
LOGIN_REDIRECT_URL = 'user_home'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pybarsys.wsgi.application'

DATABASES = {
    'default': env.db()
}

AUTH_USER_MODEL = 'barsys.User'  # custom Barsys user model

# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = env("LANGUAGE_CODE")
if not len(LANGUAGE_CODE.split("-")) == 2:
    raise environ.ImproperlyConfigured("LANGUAGE_CODE must have the form ab-cd!")
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Theme
CRISPY_TEMPLATE_PACK = 'bootstrap3'
BOOTSTRAP3 = {
    "css_url": STATIC_URL + 'barsys/bootstrap-3.3.7-dist/css/bootstrap.min.css',
    "javascript_url": STATIC_URL + 'barsys/bootstrap-3.3.7-dist/js/bootstrap.min.js',
    'jquery_url': STATIC_URL + 'barsys/jquery/jquery.min.js',
    'theme_url': STATIC_URL + 'barsys/bootstrap-3.3.7-dist/css/bootstrap-theme.css',
}

# Security
SECRET_KEY = env('SECRET_KEY')
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])
DEBUG = env.bool("DEBUG", default=False)

# Debugging
if DEBUG:
    # only set some special settings if in debug mode
    TEMPLATES[0]["OPTIONS"]["string_if_invalid"] = "!INVALID!"
    if env.bool("SHOW_DEBUG_TOOLBAR", default=False):
        INSTALLED_APPS.append('debug_toolbar')
        DEBUG_TOOLBAR_CONFIG = {
            'SHOW_TOOLBAR_CALLBACK': lambda e: True,
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

# Email
# Encode special characters with urllib.parse.quote("@:xyz?!")!
EMAIL_CONFIG = env.email_url('EMAIL_URL')

vars().update(EMAIL_CONFIG)
if env("EMAIL_FROM_ADDRESS", default="") != "":
    EMAIL_FROM_ADDRESS = env("EMAIL_FROM_ADDRESS")


class PybarsysPreferences:
    """
    Pybarsys-specific settings - more details see `docs/settings.md`
    """
    class EMAIL:
        # subfolder in barsys/templates
        TEMPLATE_DIR = env("PYBARSYS_EMAIL_TEMPLATE_DIR",
                           default="email")

        # Subject of an invoice mail
        INVOICE_SUBJECT = env("PYBARSYS_EMAIL_INVOICE_SUBJECT",
                              default='Invoice from Barsys bar')

        # Subject of a purchase notification to dependants
        PURCHASE_NOTIFICATION_SUBJECT = env("PYBARSYS_EMAIL_PURCHASE_NOTIFICATION_SUBJECT",
                                            default='Purchase notification from Barsys bar')

        # Subject of a payment reminder mail
        PAYMENT_REMINDER_SUBJECT = env("PYBARSYS_EMAIL_PAYMENT_REMINDER_SUBJECT",
                                       default='Payment reminder from Barsys bar')

        # Bar contact email address
        CONTACT_EMAIL = env("PYBARSYS_EMAIL_CONTACT_EMAIL",
                            default="bar@example.com")

        # Name of bar in default templates
        NAME_OF_BAR = env("PYBARSYS_EMAIL_NAME_OF_BAR",
                          default="Barsys bar")

        BANK_ACCOUNT_RECIPIENT = env("PYBARSYS_EMAIL_BANK_ACCOUNT_RECIPIENT",
                                     default="Barsys bar")
        BANK_ACCOUNT_NUMBER = env("PYBARSYS_EMAIL_BANK_ACCOUNT_NUMBER",
                                  default="55542")
        BANK_ACCOUNT_ROUTING_NUMBER = env("PYBARSYS_EMAIL_BANK_ACCOUNT_ROUTING_NUMBER",
                                          default="2718")
        BANK_ACCOUNT_BANK = env("PYBARSYS_EMAIL_BANK_ACCOUNT_BANK",
                                default="Royal Bank of Moldova")
        # (Display name of the invoice recipient is always appended to payment reference)
        BANK_ACCOUNT_PAYMENT_REFERENCE = env("PYBARSYS_EMAIL_BANK_ACCOUNT_PAYMENT_REFERENCE",
                                             default="Bar debts")

    class Misc:
        # Number of purchases to show on user history page
        NUM_USER_PURCHASE_HISTORY = env.int("PYBARSYS_MISC_NUM_USER_PURCHASE_HISTORY",
                                            default=15)
        # Whether to show total cost of unbilled purchases on user history page
        SUM_COST_USER_PURCHASE_HISTORY = env.bool("PYBARSYS_MISC_SUM_COST_USER_PURCHASE_HISTORY",
                                                  default=True)
        # User should transfer money if balance is below this value
        BALANCE_BELOW_TRANSFER_MONEY = Decimal(env("PYBARSYS_MISC_BALANCE_BELOW_TRANSFER_MONEY",
                                                   default='0'))
        # Number of purchases to show on main page
        NUM_MAIN_LAST_PURCHASES = env.int("PYBARSYS_MISC_NUM_MAIN_LAST_PURCHASES",
                                          default=5)
        # Number of users to show in a StatsDisplay on main page
        NUM_MAIN_USERS_IN_STATSDISPLAY = env.int("PYBARSYS_MISC_NUM_MAIN_USERS_IN_STATSDISPLAY",
                                                 default=5)
        # Whether to randomize order of StatsDisplays and show a random one first
        # (irrespective of show_by_default setting)
        SHUFFLE_STATSDISPLAY_ORDER = env.bool("PYBARSYS_MISC_SHUFFLE_STATSDISPLAY_ORDER",
                                              default=False)

        # Automatically lock account when balance is below this threshold before and after creating invoices
        BALANCE_BELOW_AUTOLOCK = Decimal(env("PYBARSYS_MISC_BALANCE_BELOW_AUTOLOCK",
                                             default='-100'))
