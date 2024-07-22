import json, os
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
from django.utils.encoding import force_str
from django.http import HttpResponse
from cdr import cdr_utils
from . import util
from . import models
from osgeo import gdal, ogr

# Functions for handling requests

# Default home page
def home(request):
    
    def load_parameters(outdict, dobj):
        # Add group if not included yet
        group = dobj.group_name
        if not group:
            group = '_'
        if group not in outdict:
            outdict[group] = [];
            
        pdict = model_to_dict(dobj)
        if dobj.only_show_with is not None:
            pdict['only_show_with'] = dobj.only_show_with.name
        outdict[group].append(pdict)

    
    # Get CRS options
    crs_opts = {c.name: model_to_dict(c) for c in models.CRS.objects.all()}
    
    ## Get commodity list
    #cdr = cdr_utils.CDR()
    #commodities = sorted([
        #x['geokb_commodity']
        #for x in cdr.get_commodity_list() if x['geokb_commodity']
    #])
    
    # Get processing step options
    processing_steps = {
        c.name: model_to_dict(c) for c in models.ProcessingStep.objects.all()
    }
    
    # Get models and model parameters
    for pp in models.ProcessingStepParameter.objects.select_related('processingstep').all():
        psname = pp.processingstep.name

        # Add model if not included yet
        if 'parameters' not in processing_steps[psname]:
            processing_steps[psname]['parameters'] = {}
            
        load_parameters(processing_steps[psname]['parameters'],pp)
    
    # Get models and model parameters
    model_opts = {}
    for mp in models.ModelParameter.objects.select_related('model').all().order_by('group_name','order'):
        modelname = mp.model.name

        # Add model if not included yet
        if modelname not in model_opts:
            model_opts[modelname] = model_to_dict(mp.model)
            model_opts[modelname]['parameters'] = {}
        
        load_parameters(model_opts[modelname]['parameters'],mp)

    
    # Get data layers
    datalayers = {} # this object sorts by category/subcategory
    datalayers_lookup = {} # this object just stores a lookup by 'name'
    for d in models.DataLayer.objects.filter(disabled=False).order_by(
        'category','subcategory','name'
        ):
        if d.category not in datalayers:
            datalayers[d.category] = {}
        if d.subcategory not in datalayers[d.category]:
            datalayers[d.category][d.subcategory] = []
        data = model_to_dict(d)
        name_pretty = d.name
        if d.name_alt:
            name_pretty = d.name_alt if ': ' not in d.name_alt else d.name_alt.split(': ')[1] 
        data['name_pretty'] = name_pretty
        datalayers[d.category][d.subcategory].append(data)
        datalayers_lookup[d.name] = data

    
    # Put any data/info you want available on front-end in this dict
    context = {
        #'COMMODITIES': json.dumps(commodities),
        #'commodities': commodities,
        'MODELS': json.dumps(model_opts),
        'DATALAYERS_LOOKUP': json.dumps(datalayers_lookup),
        'datalayers': datalayers,
        'MAPSERVER_SERVER': util.settings.MAPSERVER_SERVER,
        'crs_options': crs_opts,
        'CRS_OPTIONS': json.dumps(crs_opts),
        'PROCESSING_STEPS': json.dumps(processing_steps),
    }
    
    return render(request, 'cma/cma.html', context)

def get_metadata(request):
    
    # Get commodity list
    cdr = cdr_utils.CDR()
    commodities = sorted([
        x['geokb_commodity']
        for x in cdr.get_commodity_list() if x['geokb_commodity']
    ])

    response = HttpResponse(
        json.dumps({
            'commodities': commodities,
        })
    )
    response['Content-Type'] = 'application/json'

    return response


@csrf_exempt
def get_shp_as_geojson(request):
    '''
    Handles a POST request w/ shapefile files. Returns the vector geometry in
    geojson format.
    '''
    params = {}
    params = util.process_params(request,params,post=True)
    flist = request.FILES.getlist('file_shp')
    
    # Write the files to a temporary location
    sid = util.getUniqueID()
    files = []
    shp = None
    for f in flist:
        ext = os.path.splitext(f.name)[1]
        tf = os.path.join('/tmp',f'{sid}{ext}')
        files.append(tf)
        if ext == '.shp':
            shp = tf
        if ext == '.prj':
            prj = tf
        with open(tf, 'wb+') as destination:
            for chunk in f.chunks():
                destination.write(chunk)
                
    # Now use ogr to convert to geojson
    tmpgj = os.path.join('/tmp',f'{sid}.gj')
    gdal.VectorTranslate(tmpgj,shp,format='GeoJSON')
    
    with open(tmpgj,'r') as f:
        gj = json.loads(f.read())
    
    response = HttpResponse(
        json.dumps({
            'geojson': [gj],
            'params': params,
        })
    )
    response['Content-Type'] = 'application/json'

    return response

@csrf_exempt
def get_geojson_from_file(request):
    '''
    Handles a POST request w/ shapefile files. Returns the vector geometry in
    geojson format.
    '''
    params = {}
    params = util.process_params(request,params,post=True)
    flist = request.FILES.getlist('file_geojson')

    gj = force_str(flist[0].read())
    response = HttpResponse(
        json.dumps({
            'geojson': [json.loads(gj)],
            'params': params,
        })
    )
    response['Content-Type'] = 'application/json'

    return response

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
    
    #print(params)
    
    # Return response as JSON to client
    response = HttpResponse(json.dumps({
        'mineral_sites': sites,
        'params': params
    }))
    response['Content-Type'] = 'application/json'
    
    return response
    
    
def get_fishnet(request):
    params = {
        'resolution': 1000,
        'srid': 5070,
        'extent_wkt': '', # WKT polygon indicating AOI, in lat/lon
    }
    params = util.process_params(request, params)
    
    # Scrub the SRID input to prevent SQL-injection attacks since it will 
    # be used in raw SQL
    try:
        int(params['srid'])
    except:
        raise BadRequest("Parameter 'srid' must be an integer")
    
    # Also scrub the WKT to ensure it is valid
    extent_wkt = util.validate_wkt_geom(params['extent_wkt'])
    
    gj = util.create_fishnet(
        params['resolution'],
        params['srid'],
        clip_polygon_wkt=extent_wkt
    )
    
    data = {'param': params}
    if 'message' in gj:
        data['message'] = gj['message']
    else:
        data['geojson'] = json.loads(gj)
        
    # Return response as JSON to client
    response = HttpResponse(json.dumps(data))
    response['Content-Type'] = 'application/json'
    
    return response
