import atexit, json, os, pg, re, sys
currpath = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(currpath))
os.environ["DJANGO_SETTINGS_MODULE"] = "statmagic.settings"
import django
django.setup()
from django.conf import settings

DB = settings.DATABASES['default']

# PostgreSQL connection params
def getcon(host=DB['HOST']):
    return pg.connect(DB['NAME'],host,int(DB['PORT']), None, DB['USER'],DB['PASSWORD'])

con1 = getcon()

@atexit.register
def exit():
    if con1:
        con1.close()