'''
Backend utility code.
'''

import os
from django.conf import settings


def process_params(req,params,post=False):
    r = req.GET if not post else req.POST
    for param in params:
        if param in r:#.has_key(param):
            params[param] = r[param]
            
    return params
