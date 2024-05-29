import atexit, glob, os, pg, sys
from datetime import datetime as dt
os.environ["DJANGO_SETTINGS_MODULE"] = "statmagic.settings"
import django
django.setup()
from cma import mapfile



mapfile.write_mapfile()