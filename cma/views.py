import json, os, sys
from datetime import datetime as dt
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
from django.utils.encoding import force_str
from django.http import HttpResponse
from cdr import cdr_utils
from . import util
from . import models
from osgeo import gdal, ogr
from shapely import wkt
from shapely.geometry import mapping
from geojson_pydantic import MultiPolygon
import json

# Import cdr_schemas
if 'CDR_SCHEMAS_DIRECTORY' in os.environ:
    sys.path.append(os.environ['CDR_SCHEMAS_DIRECTORY'])
#sys.path.append('/usr/local/project/cdr_schemas/')
from cdr_schemas import prospectivity_models
from cdr_schemas import prospectivity_input

# Functions for handling requests

# Default home page
def home(request):
    
    def load_parameters(outdict, dobj):
        # Separate b/t optional/advanced and required
        reqopt = 'optional' if dobj.optional else 'required'
        if reqopt not in outdict:
            outdict[reqopt] = {}
        
        # Add group if not included yet
        group = dobj.group_name
        if not group:
            group = '_'
        if group not in outdict[reqopt]:
            outdict[reqopt][group] = [];
            
        pdict = model_to_dict(dobj)
        if dobj.only_show_with is not None:
            pdict['only_show_with'] = dobj.only_show_with.name
        outdict[reqopt][group].append(pdict)

    
    # Get CRS options
    crs_opts = {str(c.srid): model_to_dict(c) for c in models.CRS.objects.all()}
    
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
    for mp in models.ProspectivityModelTypeParameter.objects.select_related('model').all().order_by('group_name','order'):
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
        data['publication_date'] = str(data['publication_date'])[:-9]
        name_pretty = d.name
        if d.name_alt:
            name_pretty = d.name_alt if ': ' not in d.name_alt else d.name_alt.split(': ')[1] 
        data['name_pretty'] = name_pretty
        datalayers[d.category][d.subcategory].append(data)
        datalayers_lookup[d.data_source_id] = data
        

    
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
        'CDR_API_TOKEN': os.environ['CDR_API_TOKEN'],
    }
    
    return render(request, 'cma/cma.html', context)


def get_metadata(request):
    '''
    This is called by the front-end after page load so that CDR calls don't
    interupt the initial load (b/c CDR is often down). 
    '''
    
    # Initialize CDR client
    cdr = cdr_utils.CDR()
    
    # Get commodity list
    commodities = sorted(cdr.get_mineral_dedupsite_commodities())
    
    # Get deposit type list
    deposit_types = sorted([
        x['name']
        for x in cdr.get_list_deposit_types() if x['name']
    ])
    
    # Get CMA list
    cmas = {}
    for cma in cdr.get_cmas():
        if cma['mineral'] == 'test_mineral':
            continue
        
        cmas[cma['cma_id']] = cma
        
        # Reproject to WGS84
        cmas[cma['cma_id']]['extent'] = util.simplify_and_transform_geojson(
            cma['extent'],
            cma['crs'].split(':')[1],
        )
    
    response = HttpResponse(
        json.dumps({
            'commodity': commodities,
            'deposit_type': deposit_types,
            'cmas': cmas
        })
    )
    response['Content-Type'] = 'application/json'

    return response


@csrf_exempt
def get_vectorfile_as_geojson(request):
    '''
    Handles a POST request w/ shapefile OR gpkg files. Returns the vector geometry in
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
        if ext == '.gpkg':
            shp = tf
        if ext == '.prj':
            prj = tf
        with open(tf, 'wb+') as destination:
            for chunk in f.chunks():
                destination.write(chunk)
                
    ## Now use ogr to convert to geojson
    return util.convertVectorToGeoJSONresponse(shp,params)


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
    

# Function for handling CMA initiation
@csrf_exempt
def initiate_cma(request): 
    # Expected URL parameters w/ default values (if applicable)
    params = {
        'mineral': None,
        'description': None,
        'resolution': None,
        'extent': None,
        'crs': None,
    }
    params = util.process_params(request, params, post=True)
    params['resolution'] = [float(x) for x in request.POST.getlist('resolution[]')]
    params['extent'] = util.validate_wkt_geom(params['extent'])

    # convert wkt to geojson_pydantic.MultiPolygon via intermediate geoJSON
    shape = wkt.loads(params["extent"])
    geojson = mapping(shape)
    geojson['type'] = 'MultiPolygon'
    geojson['coordinates'] = [geojson['coordinates']]
    geojson_dict = json.loads(json.dumps(geojson))
    params["extent"] = MultiPolygon(**geojson_dict)
    
    # TODO: code to initiate CMA to CDR, returning cma_id
    cdr = cdr_utils.CDR()
    response = cdr.run_query("prospectivity/cma", POST=params)
    
    return response

@csrf_exempt
def submit_model_run(request):
    # Expected URL parameters w/ default values (if applicable)
    params = {
        'cma_id': None,
        'model': None,
        #'system': '',
        #'system_version': '',
        #'author': '',
        #'organization': None,
        #'model_type': None,
        'train_config': {},
        'evidence_layers': []
    }
    params = util.process_params(request, params, post_json=True)
    
    # TODO: should this model meta info should come from the CDR database 
    #       entries? For now, it's coming from the GUI db
    #       GUI database entries
    
    
    model = models.ProspectivityModelType.objects.filter(name=params['model']).first()
   
    # TODO: some code to send this off to the SRI/Beak servers
    if model.name == 'beak_som':
        train_config = params['train_config']
        
        train_config['size'] = train_config['dimensions_x']
        
        print(params['evidence_layers'])
        
        evidence_layers = []
        for el in params['evidence_layers']:
            dl = models.DataLayer.objects.filter(
                data_source_id=el['data_source_id']
            ).first()
            
            # TODO: this is all hard coded for now.......
            #       Before fixing, schema limitations need to be addressed:
            #           * enforced order (transform -> scaling -> impute)
            #           * all steps REQUIRED
            tms = el['transform_methods']
            tms = [
                'log',
                'minmax',
                prospectivity_input.Impute(
                    impute_method='mean',
                    window_size=[3,3]
                )
            ]
            #for tm in tms:
                # Get defaults if none are 
            
            l = prospectivity_input.DefineProcessDataLayer(
                cma_id = params['cma_id'],
                data_source_id = el["data_source_id"],
                title = dl.name,
                transform_methods = tms#[
                    #"log",
                    #"minmax",
                    #Impute(impute_method="mean", window_size=[3,3])
                #]
            )
            evidence_layers.append(l)

        
        beak_model_run = prospectivity_input.CreateProspectModelMetaData(
            cma_id=params['cma_id'],
            system="",
            system_version="",
            author=model.author,
            date=str(dt.now().date()),
            organization=model.organization,
            model_type=model.model_type,
            train_config=prospectivity_input.SOMTrainConfig(
                **train_config
                #size=20,
                #dimensions_x=20,
                #dimensions_y=20,
                #num_initializations=5,
                #num_epochs=10,
                #grid_type=SOMGrid.RECTANGULAR,
                #som_type=SOMType.TOROID,
                #som_initialization=SOMInitialization.RANDOM,
                #initial_neighborhood_size=0.0,
                #final_neighborhood_size=1.0,
                #neighborhood_function=NeighborhoodFunction.GAUSSIAN,
                #gaussian_neighborhood_coefficient=0.5,
                #learning_rate_decay=LearningRateDecay.LINEAR,
                #neighborhood_decay=NeighborhoodDecay.LINEAR,
                #initial_learning_rate=0.1,
                #final_learning_rate=0.01
            ),
            evidence_layers=evidence_layers
        )
    
    # TODO: some code to:
    #   (a) Send to CDR, return a job ID that the browser client can check
    #       status of and request outputs for once completed
    
    model_run_id = 1
    
    # (if staying attached) Returns JSON w/ ID indicating model run
    response = HttpResponse(json.dumps({
        'model_run_id': model_run_id,
    }))
    response['Content-Type'] = 'application/json'
    
    return response
    
    

# Function for retrieving and returning a list of mineral sites to frontend
def get_mineral_sites(request):
    params = {
        'deposit_type': '',
        'commodity': 'copper', # Commodity to search for
        'limit': 100,
        'wkt': '' # WKT polygon indicating AOI
        # [...] insert other query params
    }
    params = util.process_params(request, params)
    
    params['wkt'] = util.validate_wkt_geom(params['wkt'])
    gj = util.convert_wkt_to_geojson(params['wkt'])
    
    # Account for multipolygons by changing type to Polygon and grabbing 1st 
    # polygon in multipolygon set
    if gj['type'] == 'MultiPolygon':
        gj['type'] = 'Polygon';
        gj['coordinates'] = gj['coordinates'][0]

    # Query sites from CDR
    cdr = cdr_utils.CDR()
    sites = cdr.get_mineral_sites_search(
        commodity=params['commodity'],
        candidate=params['deposit_type'],
        bbox_polygon=json.dumps(gj),
        limit=int(params['limit'])
    )
    
    # Convert to geoJSON
    sites_gj = []
    for site in sites:
        gj_point = util.convert_wkt_to_geojson(site['location']['geom'])
        sites_gj.append({
            'type': 'Feature',
            'properties': site,
            'geometry': gj_point
        })

    # Return response as JSON to client
    response = HttpResponse(json.dumps({
        'mineral_sites': sites_gj,
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
