import json
from django.shortcuts import render
from cdr import cdr_utils
from . import util

# Functions for handling requests

# Default home page
def home(request):
    
    # Get commodity list
    cdr = cdr_utils.CDR()
    commodities = sorted([
        x['geokb_commodity']
        for x in cdr.get_commodity_list() if x['geokb_commodity']
    ])
    
    # Put any data/info you want available on front-end in this dict
    context = {
        'COMMODITIES': json.dumps(commodities)
    }
    
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
    
    # TODO: some code to send this off to the CDR's SRI/Beak worker
    
    # TODO: some code to either:
    #   (a) if staying attached, process the response
    #   (b) if detaching, send a job ID that the browser client can check
    #       status of and request outputs for once completed


# Function for retrieving and returning a list of mineral sites to frontend
def get_mineral_sites(request):
    params = {
        'commodity': 'copper', # Commodity to search for
        'wkt': '' # WKT polygon indicating AOI
        # [...] insert other query params
    }
    params = util.process_params(request, params)
    
    
    # TODO: construct and fire off query to the Knowledge graph, then filter
    #       the results by geometry (if provided)
    sites = None
    
    
    # Return response as JSON to client
    response = HttpResponse(json.dumps({
        'mineral_sites': mineral_sites,
        'params': params
    }))
    response['Content-Type'] = 'application/json'
    
    return response
    
