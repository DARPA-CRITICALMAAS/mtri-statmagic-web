"""
WSGI config for statmagic project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os, sys, site

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

############################
# Virtual environment setup

ALLDIRS = [
    '/usr/local/pythonenv/mtri-statmagic-web-env/lib/python3.10/site-packages/',
    BASE_DIR
]

# Remember original sys.path
prev_sys_path = list(sys.path)


# Add each new site-packages directory
for directory in ALLDIRS:
    site.addsitedir(directory)
    
# Reorder sys.path so new directories are at the front
new_sys_path = []
for item in list(sys.path): 
    if item not in prev_sys_path: 
        new_sys_path.append(item) 
        sys.path.remove(item) 
sys.path[:0] = new_sys_path


os.environ["DJANGO_SETTINGS_MODULE"] =  "statmagic.settings"
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
