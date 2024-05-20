from django.shortcuts import render
from . import util

# Functions for handling requests

# Default home page
def home(request):
    
    # Put any data/info you want available on front-end in this dict
    context = {}
    
    return render(request, 'cma/cma.html', context)



# Function for handling CMA model run submissions
def run_cma_model(request): 
    params = {
        'layers': [],
        'model': 'beak_ann',
        'wkt': ''
    }
    params = util.process_params(request, params, post=True)
    
    # TODO: some code to send this off to the CDR's MTRI worker 
    
