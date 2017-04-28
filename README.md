# pybarsys
A beverage shopping system for bars of small private organizations

# Installation
1. Download pybarsys into e.g. /var/www/pybarsys
2. Setup virtualenv
```bash
cd /var/www/
virtualenv -p python3 pybarsys
cd pybarsys
source bin/activate # active virtualenv
pip3 install -r requirements.txt
# Optional: test with builtin server
python3 manage.py runserver
# CTRL+C

```
