# Pybarsys settings
## General
The settings of pybarsys (and related Django settings like for email or static files) are stored in a `.env` file.
A template of this file is provided to you as `.env.example` - you can just copy it, rename it to `.env`, and modify or add settings.

A valid `.env` file should look similar to this:

```dotenv
# Comment
NAME="Pete Multicity"
NAME_TWO=Jessica Monorail
VALUE_ONE=1
VALUE_TWO=2.0
```

Note that all lines, except comments, have the structure `PARAMETER_NAME=VALUE_YOU_WANT` without any spaces next to the `=`.
Strings can be enclosed with apostrophes, but it is important that you do NOT add a comment into a line that's also supposed to be a definition (as `django-environ` will parse everything to the right as part of the string...):
```dotenv
## BAD:
NAME="Pete Multicity" # commenting here will be an issue

## GOOD:
# Commenting in an extra line is fine
NAME_TWO="Jessica Monorail"

## ALSO GOOD:
# Apostrophes for strings are not necessary with django-environ - maybe it's even better this way because you're less likely to mistakenly add a comment to a line like this?
NAME_THREE=Sri Unquoted Mueller
```

## Database and email URLs

The configuration of the database connection and email server must be supplied as URLs.
Some examples can be found in [the `django-environ` documentation](https://django-environ.readthedocs.io/en/latest/#supported-types).

It is important that special characters in these URLs are encoded.
If e.g. the username for the database connections is `user` and the password is `hunter2!"§$%&/()=?`, the encoded form of the password can be found like this:

```python
>>> import urllib.parse
>>> urllib.parse.quote('hunter2!"§$%&/()=?')
'hunter2%21%22%C2%A7%24%25%26/%28%29%3D%3F'
```

The `DATABASE_URL` could then possibly be defined like this:
```dotenv
DATABASE_URL=mysql://user:hunter2%21%22%C2%A7%24%25%26/%28%29%3D%3F@localhost:3306/database22
```

The same goes for `EMAIL_URL`.

## Required settings
These settings MUST be set in your `.env` file. If your secret key starts with a '$' you need to escape it with a backslash '\$', otherwise Django-environ will interpret it as en environment variable.

| Parameter name | Example | Description | Other examples |
| ---            | ---     | ---         | --- |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | Database settings - see [here](https://django-environ.readthedocs.io/en/latest/#supported-types) | `mysql://user:%23password@127.0.0.1:3306/dbname`
| `EMAIL_URL` | `smtp+tls://user:hunter2%40%3Axyz%3F%21@localhost:587` | Email server settings - see [here](https://django-environ.readthedocs.io/en/latest/#supported-types) | `consolemail://` |
| `LANGUAGE_CODE` | `en-us` | Language setting, used e.g. for the currency. Must have dash in the middle. The email template language needs to be set separately. | `de-de`, `nl-nl`, `en-gb` | 
`TIME_ZONE` | `Europe/Berlin` | Time zone, see [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) | `Europe/Amsterdam`, `America/New_York` |
| `SECRET_KEY` | `&_cx6qdzz^1w%per*z6emn$*&937j-^0@q93g+t9fk7hy%8p(%` | Secret key, see [here](https://docs.djangoproject.com/en/3.1/ref/settings/#std:setting-SECRET_KEY) | - |

## Optional settings
These settings can optionally be set in your `.env` file.

### General

| Parameter name | Default | Description | Other examples |
| ---            | ---     | ---         | --- |
| `DEBUG` | `off` | Whether debug mode is on (set to off for production!) | `on` |
| `SHOW_DEBUG_TOOLBAR` | `off` | Whether to show debug toolbar if debug mode is on | `on` |
| `ALLOWED_HOSTS` | `*` | By which host name the Django instance can be accessed | `localhost,server-23` |
| `STATIC_ROOT` | `static/` | Folder where `./manage.py collectstatic` collects static files | - |
| `STATIC_URL` | `/static/` | URL of static files | - |
| `SESSION_COOKIE_NAME` | `pybarsys` | Name of cookie | `pybarsys-custom` |
| `EMAIL_FROM_ADDRESS` | - | Custom `FROM` address for mails | `no-reply@example.com` |

### Pybarsys customization
### Emails
| Parameter name | Default | Description | Other examples |
| ---            | ---     | ---         | --- |
| `PYBARSYS_EMAIL_TEMPLATE_DIR` | `email` (en) | Email template folder to use (subfolder in `barsys/templates`) | `email_german`, `email_dutch` |
| `PYBARSYS_EMAIL_INVOICE_SUBJECT` | `Invoice from Barsys bar` | Subject of an invoice mail | - |
| `PYBARSYS_EMAIL_PURCHASE_NOTIFICATION_SUBJECT` | `Purchase notification from Barsys bar` | Subject of a purchase notification mail to dependants | - |
| `PYBARSYS_EMAIL_PAYMENT_REMINDER_SUBJECT` | `Payment reminder from Barsys bar` | Subject of a payment reminder mail | - |
| `PYBARSYS_EMAIL_CONTACT_EMAIL` | `bar@example.com` | Bar contact email address | - |
| `PYBARSYS_EMAIL_NAME_OF_BAR` | `Barsys bar` | Name of bar in mails | `Orange Bar` |
| `PYBARSYS_EMAIL_BANK_ACCOUNT_RECIPIENT` | `Barsys bar` | Bank account details | - |
| `PYBARSYS_EMAIL_BANK_ACCOUNT_NUMBER` | `55542` | Bank account details | - |
| `PYBARSYS_EMAIL_BANK_ACCOUNT_ROUTING_NUMBER` | `2718` | Bank account details | - |
| `PYBARSYS_EMAIL_BANK_ACCOUNT_BANK` | `Royal Bank of Moldova` | Bank account details | - |
| `PYBARSYS_EMAIL_BANK_ACCOUNT_PAYMENT_REFERENCE` | `Bar debts` | Payment reference in bank transfers. Name of invoice recipient is always appended. | `Cookies` |

### Misc
| Parameter name | Default | Description | Other examples |
| ---            | ---     | ---         | --- |
| `PYBARSYS_MISC_NUM_USER_PURCHASE_HISTORY` | `15` | Number of purchases to show on user history page | `2` |
| `PYBARSYS_MISC_SUM_COST_USER_PURCHASE_HISTORY` | `on` | Whether to show total cost of unbilled purchases on user history page | `off` |
| `PYBARSYS_MISC_BALANCE_BELOW_TRANSFER_MONEY` | `0` | User should transfer money if balance is below this value | `20` |
| `PYBARSYS_MISC_NUM_MAIN_LAST_PURCHASES` | `5` | Number of purchases to show on main page | - |
| `PYBARSYS_MISC_NUM_MAIN_USERS_IN_STATSDISPLAY` | `5` | `Number of users to show in a StatsDisplay on main page` | - |
| `PYBARSYS_MISC_SHUFFLE_STATSDISPLAY_ORDER` | `off` | Whether to randomize order of StatsDisplays and show a random one first (irrespective of `show_by_default` setting) | `on` |
| `PYBARSYS_MISC_BALANCE_BELOW_AUTOLOCK` | `-100` | Automatically lock account when balance is below this threshold before and after creating invoices | `0` |
