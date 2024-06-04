'''
Backend utility code.
'''

import os, random, string
from datetime import datetime as dt
from django.conf import settings


def process_params(req,params,post=False):
    r = req.GET if not post else req.POST
    for param in params:
        if param in r:#.has_key(param):
            params[param] = r[param]
            
    return params

def getUniqueID():
    '''
    UniqueID is time of creation + 6 random characters
    '''
    return '{}_{}'.format(
        dt.now().strftime('%Y%m%d%H%M'),
        ''.join(
            random.SystemRandom().choice(
                string.ascii_uppercase + string.digits
                ) for _ in range(4)
            )
        )
