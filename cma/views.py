from django.shortcuts import render
from . import util

# Functions for handling requests

# Default home page
def home(request):
    
    # Put any data/info you want available on front-end in this dict
    context = {}
    
    return render(request, 'cma/cma.html', context)


# Function for handling datacube creation requests
def create_datacube(request): 
    params = {
        'layers': [], # list of layers to include in the data cube
        'wkt': '' # WKT representing polygon geometry indicating AOI
    }
    params = util.process_params(request, params, post=True)
    
    # TODO: some code to send this off to the CDR's MTRI datacube worker 
    
    # TODO: some code to either:
    #   (a) if staying attached, process the response
    #   (b) if detaching, send a job ID that the browser client can check
    #       status of and request outputs once completed
    
    
    # (if staying attached) Returns JSON w/ datacube_id
    response = HttpResponse(json.dumps({
        'datacube_id': datacube_id,
    }))
    response['Content-Type'] = 'application/json'
    
    return response
    

# Function for handling CMA model run submissions
def run_cma_model(request): 
    params = {
        'datacube_id': '', # ID indicating a datacube
        'model': 'beak_ann', # One of Beak or SRI's models
    }
    params = util.process_params(request, params, post=True)
    
    # TODO: some code to send this off to the CDR's SRI/beak worker
    
    # TODO: some code to either:
    #   (a) if staying attached, process the response
    #   (b) if detaching, send a job ID that the browser client can check
    #       status of and request outputs for once completed
    
    
    
