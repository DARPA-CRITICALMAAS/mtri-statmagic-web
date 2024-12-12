import atexit, glob, os, pg, sys
from datetime import datetime as dt
currpath = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(currpath))
os.environ["DJANGO_SETTINGS_MODULE"] = "statmagic.settings"
import django
django.setup()
from cma import mapfile


mapfile.write_mapfile()