import json, os, sys
import pandas as pd
import geopandas as gpd
from django.core.exceptions import BadRequest
from datetime import datetime as dt
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
from django.utils.encoding import force_str
from django.http import HttpResponse
from django.core.cache import cache
from cdr import cdr_utils
from . import util
from . import models
from . import mapfile
from io import StringIO
from osgeo import gdal, ogr
from shapely import wkt
from shapely.geometry import mapping
import rasterio
from geojson_pydantic import MultiPolygon
import json

# Import cdr_schemas
if 'CDR_SCHEMAS_DIRECTORY' in os.environ:
    sys.path.append(os.environ['CDR_SCHEMAS_DIRECTORY'])
    #print('CDR_SCHEMAS_DIRECTORY',os.environ['CDR_SCHEMAS_DIRECTORY'])
#sys.path.append('/usr/local/project/cdr_schemas/')
from cdr_schemas import prospectivity_models
from cdr_schemas import prospectivity_input

# Functions for handling requests


# Default home page
def home(request):
    
    # TA1 system/version combos
    # **NOTE: hard-coded for now; only way to get these from CDR is to 
    #         aggregate from the get_tiles_sources results
    ta1_systems = {
        'uiuc-golden-muscat': ['0.4.2'],
        'umn-usc-inferlink': ['0.0.4', '0.0.5', '0.0.6'],
        'uncharted-area': ['0.0.4']
    }
    
    # Get CRS options
    crs_opts = {str(c.srid): model_to_dict(c) for c in models.CRS.objects.all()}
    
    # Get processing step options
    processing_steps = util.get_processing_steps()
    
    # Get models and model parameters
    model_opts = {}
    for mp in models.ProspectivityModelTypeParameter.objects.select_related('model').all().order_by('group_name','order'):
        modelname = mp.model.name

        # Add model if not included yet
        if modelname not in model_opts:
            model_opts[modelname] = model_to_dict(mp.model)
            model_opts[modelname]['parameters'] = {}
        
        util.load_parameters(model_opts[modelname]['parameters'],mp)

    # Get data layers
    dls = util.get_datalayers_for_gui(
        include_outputlayers=False,
        include_processedlayers=False
    )
    
    # Put any data/info you want available on front-end in this dict
    context = {
        #'COMMODITIES': json.dumps(commodities),
        #'commodities': commodities,
        'MODELS': json.dumps(model_opts),
        'DATALAYERS_LOOKUP': json.dumps(dls['datalayers_lookup']),
        'datalayers': dls['datalayers'],
        'MAPSERVER_SERVER': util.settings.MAPSERVER_SERVER,
        'crs_options': crs_opts,
        'CRS_OPTIONS': json.dumps(crs_opts),
        'PROCESSING_STEPS': json.dumps(processing_steps),
        'CDR_API_TOKEN': os.environ['CDR_API_TOKEN'],
        'TA1_SYSTEMS': json.dumps(ta1_systems),
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
    #cs = [
        #'Cerium',
        #'Cobalt',
        #'Copper',
        #'Dysprosium',
        #'Erbium',
        #'Europium',
        #'Gadolinium',
        #'Gallium',
        #'Germanium',
        #'Gold',
        #'Holmium',
        #'Indium',
        #'Lanthanum',
        #'Lithium',
        #'Lutetium',
        #'Molybdenum',
        #'Neoymium',
        #'Nickel',
        #'Praseodymium',
        #'Rare earth elements',
        #'Rhenium',
        #'Samarium',
        #'Scandium',
        #'Silver',
        #'Tellurium',
        #'Terbium',
        #'Thulium',
        #'Tungsten',
        #'Ytterbium',
        #'Yttrium',
        #'Zinc',
    #]
    cs = cdr.get_mineral_dedupsite_commodities()
    if 'rare earth elements' not in cs:
        cs.append('Rare earth elements')
    commodities = sorted(cs)
    
    # Get deposit type list
    deposit_types = sorted([
        x['name']
        for x in cdr.get_list_deposit_types() if x['name']
    ])

    # Get CMA list
    cmas = {}
    for cma in cdr.get_cmas():
        if ('test_' in cma['mineral'] or 
            ('Surprise' in cma['description'] and cma['resolution'][0] == 1000.0) or 
            cma['mineral'] in ('mvt_Test','mvt_Test2') or
            cma['description'] in ('mvttest3','Tungsten_2024-08-30')
        ):
            continue
        #print(cma)
        cma = util.process_cma(cma)        
        cmas[cma['cma_id']] = cma

    # vvv This is now only done when loading a CMA to avoid unnecessary calls to
    #     CDR
    ## Get model runs and attach to CMAs 
    #for cma_id,cma in cmas.items():
        #cma['model_runs'] = []
        #for mr in cdr.get_model_runs(cma_id):
            #cma['model_runs'].append(mr['model_run_id'])
    
    
    response = HttpResponse(
        json.dumps({
            'commodity': commodities,
            'top1_deposit_type': deposit_types,
            'cmas': cmas
        })
    )
    response['Content-Type'] = 'application/json'

    return response


@csrf_exempt
def upload_datalayer(request):
    '''
    Handles a POST request w/ shapefile OR gpkg files. Returns the vector geometry in
    geojson format.
    '''
    params = {
        'doi': '',
        'author': '',
        'publication_date': '',
        'description': '',
        'reference_url': '',
        'category': 'geophysics',
        'subcategory': 'User upload',
        'type': 'continuous',
        'derivative_ops': '',
    }
    params = util.process_params(request,params,post=True)
    if not params['publication_date']:
        params['publication_date'] = dt.now().strftime('%Y-%m-%d')
    else:
        try:
            dt.strptime(params['publication_date'], '%Y-%m-%d')
        except:
            msg = f'publication_date "{params["publication_date"]}" is invalid; must be YYYY-MM-DD format'
            return HttpResponse(msg, status=400)
    
    f = request.FILES.getlist('file')[0]
    fread = f.read()

    # Extract spatial resolution and prj from file
    sid = util.getUniqueID()
    memtif = f'/vsimem/{sid}.tif'
    gdal.FileFromMemBuffer(memtif, fread)
    res = int(util.get_tif_resolution(memtif))
    ds = gdal.Open(memtif)
    prj = ds.GetProjection()
    del ds
    gdal.Unlink(memtif)
    
    if not prj:
        msg = f'upload file "{f.name}" has no projection'
        return HttpResponse(msg, status=400)
    
    # Cogify
    #gdal.FileFromMemBuffer(memtif, fread)
    # TODO: add step to convert type based on data type
    #   * e.g. binary should be a reduced type
    cogfile_bytes = util.cogify_from_buffer(fread)
    
    # Get date
    #date = 

    # Create CDR metadata object
    ds = prospectivity_input.CreateDataSource(
        DOI = params['doi'],
        authors = params['author'].split(','),
        publication_date = params['publication_date'],
        category = params['category'],
        subcategory = params['subcategory'],
        description = params['description'],
        derivative_ops = params['derivative_ops'],
        type = params['type'],
        resolution = [res,res],
        format = 'tif',
        reference_url = params['reference_url'],
        evidence_layer_raster_prefix = params['description'],
    )


    # Post to CDR
    print('Posting to CDR...')
    cdr = cdr_utils.CDR()
    res = cdr.post_prospectivity_data_source(
        input_file=cogfile_bytes.read(),#open(cogfile_bytes,'rb'),#open(cogfile,'rb').read(),#fread,#f.read(),
        metadata=ds.model_dump_json(exclude_none=True)
    )
    #os.remove(cogfile_bytes)

    dsid = res['data_source_id']
    print('data_source_id from CDR: ',dsid)
    
    # Sync to GUI db:
    util.sync_cdr_prospectivity_datasources_to_datalayer(
        data_source_id = dsid
    )
    
    # Rewrite mapfile so it shows up in tile server 
    mapfile.write_mapfile()
    
    # Send layer entry to GUI 
    dl = util.get_datalayers_for_gui(data_source_ids=[dsid])['datalayers_lookup']
    
    print(dsid,dl)
    
    response = HttpResponse(
        json.dumps({
            'datalayer': dl[list(dl.keys())[0]],
        })
    )
    response['Content-Type'] = 'application/json'

    return response
 
 
def get_model_run(request):
    params = {
        'model_run_id': None,
    }
    params = util.process_params(request,params)
    
    cdr = cdr_utils.CDR()
    res = cdr.get_model_run(params['model_run_id'])
    
    response = HttpResponse(
        json.dumps({
            'params': params,
            'model_run': res,
        })
    )
    response['Content-Type'] = 'application/json'

    return response

def get_model_runs_for_cma(request):
    params = {
        'cma_id': '',
    }
    params = util.process_params(request,params)
    
    mrs = []
    for mr in cdr.get_model_runs(params['cma_id']):
        mrs.append(mr['model_run_id'])
        
    # While we're at it, check CDR and sync any outputs not yet present
    dsids = util.sync_cdr_prospectivity_outputs_to_outputlayer(
        cma_id = params['cma_id']
    )
    
    dls = util.get_datalayers_for_gui()
    
    response = HttpResponse(
        json.dumps({
            'params': params,
            'model_runs': mrs,
            'DATALAYERS_LOOKUP_UPDATES': json.dumps(dls['datalayers_lookup']),
        })
    )
    response['Content-Type'] = 'application/json'

    return response

def sync_model_outputs(request):
    params = {
        'cma_id': '',
        #'model_runs': None,
    }
    params = util.process_params(request,params)
    
    # NOTE: commenting out the sync step now b/c much better to let the cron
    #       take care of this detached from front-end. Instead just do a fresh
    #       database check for any new model outputs for the given CMA ID
    ## Check CDR and sync any outputs not yet present
    #dsids = util.sync_cdr_prospectivity_outputs_to_outputlayer(
        #cma_id = params['cma_id']
    #)
 
    response = HttpResponse(
        json.dumps({
            'params': params,
            'DATALAYERS_LOOKUP_UPDATES': util.load_new_layers(
                #dsids,
                include_processedlayers=True,
                cma_id=params['cma_id']
            ),
        })
    )
    response['Content-Type'] = 'application/json'

    return response

def sync_processed_layers(request):
    params = {
        'event_id': '',
        'cma_id': '',
        #'model_runs': None,
    }
    params = util.process_params(request,params)
    
    # NOTE: commenting out the sync step now b/c much better to let the cron
    #       take care of this detached from front-end. Instead just do a fresh
    #       database check for any new model outputs for the given CMA ID
    ## Check CDR and sync any outputs not yet present
    #dsids = util.sync_cdr_prospectivity_outputs_to_outputlayer(
        #cma_id = params['cma_id']
    #)
    
    layers = util.load_new_layers(
        #dsids,
        include_outputlayers=False,
        include_processedlayers=True,
        cma_id=params['cma_id'],
        event_id=params['event_id'],
    )
    #print(layers)
    msg = 'No additional layers currently available'
    
     # Get mapfile content
    with open(mapfile.get_mapfile_path(),'r') as f:
        mapfile_content = f.read()
    
    # Check to see if layers have been processed for GUI yet; if not, delay
    # sending to front-end until they are fully processed
    delay = False
    for dsid,layer in layers.items():
        #dsid = layer['data_source_id']
        
        # Check if layer is sync'd locally 
        if not os.path.exists(util.get_output_layer_local_sync_path(dsid)):
            msg = 'Processed layer(s) available; optimizing for visualization...'
            delay = True
            break

        # Check to see if all layers are in mapfile
        if mapfile.scrub_wms_layername(dsid) not in mapfile_content:
            msg = 'Extracting stats/extent for map visualization...'
            delay = True
            break
        
    if delay:
        layers = {}
    
    response = HttpResponse(
        json.dumps({
            'params': params,
            'DATALAYERS_LOOKUP_UPDATES': layers,
            'model_run_status': msg,
        })
    )
    response['Content-Type'] = 'application/json'

    return response


def check_model_run_status(request):
    params = {
        'model_run_id': '',
    }
    params = util.process_params(request,params)
    
    # Get list of outputs associated w/ model_run
    cdr = cdr_utils.CDR()
    res = cdr.get_prospectivity_output_layers(**params)
    
    # Get local database content 
    dsids = [x[0] for x in  
        models.OutputLayer.objects.filter(
            model_run_id=params['model_run_id']
        ).values_list('data_source_id')
    ]
    
    msg = 'No additional model outputs currently available'
    
    n_complete = 0
    if len(res) == 0:
        msg = 'No model outputs available...'
    else:
        # Get mapfile content
        with open(mapfile.get_mapfile_path(),'r') as f:
            mapfile_content = f.read()
        
        for ol in res:
            #print(ol)
            dsid = ol['layer_id']
            
            # Check if layer is in database
            if dsid not in dsids:
                print(dsids)
                print(dsid)
                msg = 'Unprocessed outputs available; syncing with GUI...'
                break

            # Check if layer is sync'd locally 
            if not os.path.exists(util.get_output_layer_local_sync_path(dsid)):
                msg = 'Unprocessed model outputs available; optimizing for visualization...'
                break
        
            # Check to see if all layers are in mapfile
            if mapfile.scrub_wms_layername(dsid) not in mapfile_content:
                msg = 'Extracting model output stats/extent for map visualization...'
                break

            # Track layers that made it through all the checks w/out breaking
            n_complete += 1

    response = HttpResponse(
        json.dumps({
            'params': params,
            'complete': n_complete == len(res),
            'DATALAYERS_LOOKUP_UPDATES': util.load_model_outputs(dsids),
            'model_run_status': msg,
        })
    )
    response['Content-Type'] = 'application/json'

    return response


def get_model_runs(request):
    '''
    Returns list of model run metadata for the provided model_runs (comma 
    separated list)
    '''
    params = {
        'cma_id': '',
        #'model_runs': None,
    }
    params = util.process_params(request,params)
    
    cdr = cdr_utils.CDR()
    
    # Get model runs and attach to CMAs
    model_runs = {}
    for mr in cdr.get_model_runs(params['cma_id']):
        run = cdr.get_model_run(mr['model_run_id'])
        # Filter out model runs from pre-2024-10-24 b/c that is when the 
        # preprocess and model_run schemas were separated and the model_runs 
        # no longer fit with what is on the GUI 
        if run['event'] and run['event']['timestamp'] > '2024-10-24':
            model_runs[mr['model_run_id']] = run
        
    #While we're at it, check CDR and sync any outputs not yet present
    #dsids = util.sync_cdr_prospectivity_outputs_to_outputlayer(
        #cma_id = params['cma_id']
    #)
    
    #dls = util.get_datalayers_for_gui(data_source_ids = dsids)
    
    response = HttpResponse(
        json.dumps({
            'params': params,
            'model_runs': model_runs,
           # 'DATALAYERS_LOOKUP_UPDATES': dls['datalayers_lookup'],
        })
    )
    response['Content-Type'] = 'application/json'

    return response



def get_model_outputs(request):
    params = {
        'cma_id': '',
        'model_run_id': ''
    }
    params = util.process_params(request,params)
    
    cdr = cdr_utils.CDR()
    res = cdr.get_prospectivity_output_layers(**params)
    
    #for layer in res:
        # Load to GUI db if not there yet
        
    
    response = HttpResponse(
        json.dumps({
            'params': params,
            'model_outputs': res,
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

## Function for handling datacube creation requests
#def create_datacube(request): 
    #params = {
        #'layers': [], # list of layers to include in the data cube
        #'wkt': '' # WKT representing polygon geometry indicating AOI
    #}
    #params = util.process_params(request, params, post=True)
    
    ## TODO: some code to send this off to the CDR's MTRI datacube worker 
    
    ## TODO: some code to either:
    ##   (a) if staying attached, process the response
    ##   (b) if detaching, send a job ID that the browser client can check
    ##       status of and request outputs once completed
    
    
    ## (if staying attached) Returns JSON w/ datacube_id
    #response = HttpResponse(json.dumps({
        #'datacube_id': datacube_id,
    #}))
    #response['Content-Type'] = 'application/json'
    
    #return response
    

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
    
    #print(params['extent'])
    params['extent'] = util.validate_wkt_geom(params['extent'])

    # Convert wkt to geojson_pydantic.MultiPolygon via intermediate geoJSON

    shape = wkt.loads(params["extent"])
    geojson = mapping(shape)
    if geojson['type'] == 'Polygon':
        geojson['type'] = 'MultiPolygon'
        geojson['coordinates'] = [geojson['coordinates']]
    geojson_dict = json.loads(json.dumps(geojson))


    # Extent always comes in as 4326, so reproject and simplify while at it
    params['extent'] = util.simplify_and_transform_geojson(
        geojson_dict,
        4326,
        t_srs=params['crs'].split(':')[1]
    )

   # print(params['extent'])
    params["extent"] = MultiPolygon(**params["extent"])
    
    # Create CDR schema instance
    cma = prospectivity_input.CreateCriticalMineralAssessment(
        **params
    )
    
    cma_json = cma.model_dump_json(exclude_none=True)
    
    #print('\n\n\n\n\n')
    #print(cma_json)
    #blerg
    
    # Generate template raster
    proj4 = models.CRS.objects.filter(srid=params['crs']).values_list('proj4text')[0][0]
    tmpfile = util.build_template_raster_from_CMA(cma, proj4)
    
    # Initiate CMA to CDR, returning cma_id
    cdr = cdr_utils.CDR()
    response = cdr.post_cma(
        input_file=open(tmpfile,'rb'),#memfile,
        metadata=cma_json,
    )
    
    # And get the CMA object that was created  
    cma = util.process_cma(cdr.get_cma(response['cma_id']))
    
    #  Returns JSON w/ ID indicating model run
    response = HttpResponse(json.dumps({
        'cma': cma,
    }))
    response['Content-Type'] = 'application/json'
    
    return response


@csrf_exempt
def submit_preprocessing(request):
    # Expected URL parameters w/ default values (if applicable)
    params = {
        'cma_id': None,
        'evidence_layers': [],
        'training_sites': [],
        'dry_run': False,
    }
    params = util.process_params(request, params, post_json=True)
    vector_layers = []
    
    processing_steps = util.get_processing_steps()
    
    # Build evidence layer model instances
    evidence_layers = []
    for el in params['evidence_layers']:
        dl = models.DataLayer.objects.filter(
            data_source_id=el['data_source_id']
        ).first()
        
        print(el['data_source_id'])
        
        tms = util.process_transform_methods(
            el['transform_methods'],
            processing_steps,
        )

        # vvv NEVERMIND: mpm_input_preprocessing handles vector layers already,
        #     and including these here instead would make it hard to check that  
        #     a layer was already processed in this way
        #if dl.vector_format:
            ## TODO: build features from vector sources
            ## Actually seems like these should go into extra_geometries as 
            ## geojson b/c evidence_features DataTypeId requires an ID of a 
            ## feature already in the CDR
            #extra_geometries = []
            ##shp = util.get_output_layer_local_sync_path(
                ##el['data_source_id'],
                ##ext='shp'
            ##)
            ##print('loading:',shp)
            ##gdf = gpd.read_file(shp)
            ##print(gdf.to_json())
            ##blerg
            
            #l = prospectivity_input.DefineVectorProcessDataLayer(
                #label_raster = False,
                #title = el['data_source_id'],
                #evidence_features = [],
                #extra_geometries = extra_geometries,
                #transform_methods = tms,
            #)
            
            #vector_layers.append(l)
            
       # else:

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
       
    #vector_layers = []
    #for site_id in params['training_sites']:
    # Now do training sites
    if params['training_sites']:
        #print(params['training_sites'])
        tms = []#util.process_transform_methods(el['transform_methods'])
        extra_geometries = []
        
        evidence_features = [
            prospectivity_input.DataTypeId(
                raw_data_type = prospectivity_input.RawDataType.MINERAL_SITE,
                id=x
            ) for x in params['training_sites'] if type(x) == str
        ]
        
        # extra_geometries will be provided as list of coordinates [x,y]
        extra_geometries = [
            prospectivity_input.Point(coordinates = x)
            for x in params['training_sites'] if type(x) == list
        ]
            
        n_sites = len(evidence_features) + len(extra_geometries)
            
        ## Build vector layer model instances
        l = prospectivity_input.DefineVectorProcessDataLayer(
            label_raster = True,
            title = f'Training sites (n={n_sites})',
            evidence_features = evidence_features,
            extra_geometries = extra_geometries,
            transform_methods = tms,
        )
        
        vector_layers.append(l)
        
        
    process_data_layers = prospectivity_input.CreateProcessDataLayers(
        cma_id=params['cma_id'],
        system="statmagic",
        system_version="",
        evidence_layers=evidence_layers,
        vector_layers=vector_layers,
    )
    
    #print(vector_layers)

    print('POSTing model run to CDR:')
    #print(process_data_layers)
    #print(model_run.model_dump_json(exclude_none=True))

    
    #print(process_data_layers.model_dump_json(indent=4))
    #print(params['dry_run'])
    #blerg
    
    cdr = cdr_utils.CDR()
    print(process_data_layers.model_dump_json())
    #blerg
    #if params['dry_run']:
        #res = {'model_run_id': 'd9260cb9832f4c63abbe1f82fc4729bb'}
    #else:
    # Post to CDR
    res = cdr.post_prospectivity_preprocess(
        process_data_layers.model_dump_json()
        # model_run.model_dump_json(exclude_none=True)
    )
        
    print(res)
    #blerg
    #res2 = cdr.get_model_run(res['event_id'])

    # Return JSON w/ ID indicating model run
    response = HttpResponse(json.dumps({
        'event_id': res['event_id'],
       #'model_run': res2
    }))
    response['Content-Type'] = 'application/json'
    
    return response
    

@csrf_exempt
def submit_model_run(request):
    # Expected URL parameters w/ default values (if applicable)
    params = {
        'cma_id': None,
        'model': None,
        'train_config': {},
        'evidence_layers': [],
        'dry_run': False, # set to True to skip posting to CDR (just tests process)
    }
    params = util.process_params(request, params, post_json=True)
    
    #processing_steps = util.get_processing_steps()
    
    # TODO: should this model meta info should come from the CDR database 
    #       entries? For now, it's coming from the GUI db
    #       GUI database entries
    model = models.ProspectivityModelType.objects.filter(name=params['model']).first()
   
   
    ## TODO: rebuild this using processed layer IDs instead
    #evidence_layers = [
        #'05c9f1c74da972e277fc106221845e83__d751713988987e9331980363e24189ce_022fa85caca7865c379b2ecc5af0262f',
        #'d7848f650d28fd995bca5cf4a27b3f18__4cf3b043a38f568cb6e598efc6f08508_f8ffc0b5fe885f8301c495763f5da851',
        #'aea6cc3f76f618e5557f10916de96be6__d751713988987e9331980363e24189ce_fccb2a8aba0cbb481929f38444304b03'
    #]
   
    train_config = params['train_config']

    #train_config = {'final_learning_rate': None, 'initial_learning_rate': None}
   
    # Mapping of model name to model config schema
    model_map = {
        'sri_NN': prospectivity_input.NeuralNetUserOptions,
        'beak_som': prospectivity_input.SOMTrainConfig,
        #'jataware_rf': prospectivity_input.RFUserOptions,
    }
   
    # Build TA3 models metadata instance
    model_run = prospectivity_input.CreateProspectModelMetaData(
        cma_id=params['cma_id'],
        system="statmagic",
        system_version="",
        author=model.author,
        date=str(dt.now().date()),
        organization=model.organization,
        model_type=model.name,#,model.model_type,
        train_config=model_map[model.name](**train_config),
        evidence_layers=params['evidence_layers']
    )
    
    print('POSTing model run to CDR:')
    print(model_run)
    #print(model_run.model_dump_json(exclude_none=True))

    #print(model_run.model_type)
    #blerg

    print(model_run.model_dump_json(indent=4))
    #blerg
    
    cdr = cdr_utils.CDR()
    if params['dry_run']:
        res = {'model_run_id': 'd9260cb9832f4c63abbe1f82fc4729bb'}
    else:
        # Post to CDR
        res = cdr.post_model_run(
            model_run.model_dump_json()
           # model_run.model_dump_json(exclude_none=True)
        )
        
    res2 = cdr.get_model_run(res['model_run_id'])

    # Return JSON w/ ID indicating model run
    response = HttpResponse(json.dumps({
        'model_run_id': res['model_run_id'],
        'model_run': res2
    }))
    response['Content-Type'] = 'application/json'
    
    return response


# Function for retrieving and returning a list of mineral sites to frontend
@csrf_exempt
def get_mineral_sites(request):
    params = {
        # top group are args that go to CDR/cache:
        'commodity': 'Copper', # Commodity to search for
        'with_deposit_types_only': 'false',
        'limit': 100,
        'top_n': 1,
        
        # this next group are filters applied to what is returned from CDR 
        'type': 'Past Producer,Prospect,Producer,NotSpecified',
        'rank': 'A,B,C,U',
        'top1_deposit_type': None,
        'top1_deposit_group': None,
        'top1_deposit_classification_confidence__gte': 0.0,
        'only_gradetonnage': False,
        
        # this will be converted to bbox_polygon for CDR
        'wkt': None, # WKT polygon indicating AOI
        
        # output format
        'format': 'json'    
    }
    params = util.process_params(request, params, post_json=True)
    
    # Convert comma-separated params to lists
    for p in ('type','rank'):
        params[p] = params[p].split(',')
    
    #print(params)
    
    if params['wkt']:
        params['wkt'] = util.validate_wkt_geom(params['wkt'])
        gj = util.convert_wkt_to_geojson(params['wkt'])
    
        #print(gj)
    
        # Account for multipolygons by changing type to Polygon and grabbing 1st 
        # polygon in multipolygon set
        if gj['type'] == 'MultiPolygon':
            gj['type'] = 'Polygon';
            gj['coordinates'] = gj['coordinates'][0]
    else: # if no extent provided, default to NA coords
        #gj = {
            #"type": "Polygon",
            #"coordinates": [
                #[
                    #[-180, 7],
                    #[-180, 83.5],
                    #[-52, 83.5],
                    #[-52, 7],
                    #[-180, 7]
                #]
            #]
        #}
        gj = {
            'type': 'Polygon',
            'coordinates': (
                ((-78.50593, 6.664608), (-77.001544, 8.407168), 
                 (-76.273124, 13.581921), (-60.522853, 11.544616), 
                 (-44.950799, 51.179343), (-75.787818, 75.845169), 
                 (-72.028561, 79.496652), (-57.270212, 83.026219), 
                 (-167.606439, 83.753911), (-169.011996, 64.320872), 
                 (-173.137277, 63.587675), (-187.786318, 54.316523), 
                 (-188.752638, 51.179343), (-87.527109, 4.65308), 
                 (-78.50593, 6.664608)),)
        }


    cs = [params['commodity']]
    if params['commodity'] == 'rare earth elements':
        cs = [
            'Lanthanum', 
            'Cerium', 
            'Yttrium', 
            'Praseodymium', 
            #'Neoymium',
            'Neodymium',
            'Samarium',
            'Europium',
            'Terbium', 
            'Gadolinium',
            'Ytterbium', 
            'Dysprosium', 
            'Thulium', 
            'Lutetium',
            'Holmium', 
            'Erbium'
        ]

   # print(cs)
    sites_json = []
    sites_df_merged = None
    for c in cs:
        # Args to (a) send to CDR and (b) use as cache key
        args = {
            'commodity': c,
            'with_deposit_types_only': params['with_deposit_types_only'],
            'top_n': params['top_n'],
            'bbox_polygon': json.dumps(gj),
            'limit': int(params['limit']),
        }
        
        cache_key = util.get_cache_key('getdedupsitescdr',args)
        print('cache key:\n',cache_key)

        sites_df = cache.get(cache_key)
        if type(sites_df) is type(None) or args['limit'] > 0: # if no cache results exist or limit provided
            print(cache_key)
            print('no cache!')
            
            # Query sites from CDR
            cdr = cdr_utils.CDR()
            sites_df = cdr.get_dedup_sites_search(**args)
            
            # only cache no-limit returns
            if args['limit'] < 0:
                cache.set(cache_key,sites_df)
        else:
            print('cache found!')
        
        if type(sites_df_merged) == type(None):
            sites_df_merged = sites_df
        else:
            sites_df_merged = pd.concat([sites_df_merged,sites_df])
        
    # print(json.dumps(gj))
    
    # Apply non-CDR-based filters
    #   * TODO: also trim out unncessary properties

    
    sites_filtered = []
    #for site in sites_json:#json.loads(sites_df.to_json(orient='records')):
    for index, site in sites_df_merged.iterrows():
        # Apply grade/tonnage data filter
        #print(params['only_gradetonnage'])
        if params['only_gradetonnage'] in ('true',True,'True','t','T') and not site['grade']:
           # print('skipping!')
            continue
        
        # Apply primary deposit site confidence threshold filter
        conf_thresh = params['top1_deposit_classification_confidence__gte']
        conf = site['top1_deposit_classification_confidence']
        if conf_thresh and conf:
            if float(conf) < float(conf_thresh):
                continue
        
        # Apply other filters
        skip = False
        for p in ('rank','type','top1_deposit_type','top1_deposit_group'):
            if params[p]:
                srank = site[p]
                if not srank or srank in ('nan',) or type(srank) == float:
                    skip = True
                    continue
                if '[' in srank:
                    srank = eval(srank)
                else:
                    srank = [srank]
                matches =  [i for i in srank if i in params[p]]
                if not matches:
                    skip = True
        if skip:
            continue
        
        sites_filtered.append(site)
       

    base_name = f'StatMAGIC_{params["commodity"]}'#_{dt.now().date()}'
    
    #print('n sites filtered:',len(sites_filtered))
    
    if params['format'] == 'csv':
        sites_df_filtered = pd.DataFrame(sites_filtered,columns=sites_df_merged.columns)
        buff = StringIO()
        sites_df_filtered.to_csv(buff)
        buff.seek(0)
        response = HttpResponse(buff, content_type='application/csv')
        response['Content-Disposition'] = f'attachment; filename="{base_name}.csv'

    else:
        # Create GeoJSON of the filtered sites
        sites_gj = []
        for site in sites_filtered:
            st = json.loads(site.to_json())

            gj_point = util.convert_wkt_to_geojson(st['centroid_epsg_4326'])
            sites_gj.append({
                'type': 'Feature',
                'properties': st,
                'geometry': gj_point
            })
        #print(len(sites_gj))

        if params['format'] == 'json':
            # Return response as JSON to client
            response = HttpResponse(json.dumps({
                'mineral_sites': sites_gj,
                'params': params
            }))
            response['Content-Type'] = 'application/json'
            
        else:
            response = util.downloadVector(
                {'features': sites_gj},
                output_format=params['format'],
                base_name=base_name,
            )
    
    return response
    

def recreate_mapfile(request):
    '''
    Admin convenience function for initiating mapfile rewrite from browser.
    '''
    mapfile.write_mapfile()
    
    # Return response as JSON to client
    response = HttpResponse('Mapfile written')
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
    
    return respons

@csrf_exempt
def get_csv_column_names(request):
    lines = request.FILES.getlist('file_csv')[0].readlines()
    cols = util.clean_line(lines[0])
     
    # Return response as JSON to client
    response = HttpResponse(json.dumps(cols))
    response['Content-Type'] = 'application/json'

    return response

@csrf_exempt 
def upload_sites_csv(request):
    params = {
        'csv_longitude_field': '',
        'csv_latitude_field': '',
    }
    params = util.process_params(request, params, post_json=True)

    lines = request.FILES.getlist('file_csv')[0].readlines()
    hdr = util.clean_line(lines[0])

    coords = []
    for line in lines[1:]:
        ln = clean_line(line)
        lat = ln[hdr.index(params['csv_latitude_field'])]
        lon = ln[hdr.index(params['csv_longitude_field'])]
        coords.append([lon,lat])
        
     # Return response as JSON to client
    response = HttpResponse({
        'site_coords': json.dumps(coords)
    })
    response['Content-Type'] = 'application/json'

    return response 
        
                 

@csrf_exempt
def download_model_outputs(request):
    params = {
        'urls': [],
        'cma_name': '',
        'model_run_id': '',
    }
    params = util.process_params(request, params, post_json=True)

    return util.download_model_outputs(
        params['urls'],
        params['cma_name'],
        params['model_run_id']
    )

