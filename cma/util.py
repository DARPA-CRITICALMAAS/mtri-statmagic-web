'''
Backend utility code.
'''
import glob, json, math, os, random, re, requests, shutil, string, sys, tempfile, zipfile
from pathlib import Path
from io import BytesIO
from numbers import Number
import geopandas as gpd
from urllib.request import urlopen
from shapely.geometry import box
import xarray, pyproj
from datetime import datetime as dt
from osgeo import gdal, ogr, osr
import numpy as np
from cdr import cdr_utils
from django.conf import settings
from django.forms.models import model_to_dict
from django.core.exceptions import BadRequest
from django.http import HttpResponse
from django.db import connection
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from . import models
from . import mapfile
from shapely import geometry, wkt
from shapely.geometry import mapping
import rasterio as rio
from rasterio.crs import CRS
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.features import rasterize
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles


# Import cdr_schemas
if 'CDR_SCHEMAS_DIRECTORY' in os.environ:
    sys.path.append(os.environ['CDR_SCHEMAS_DIRECTORY'])
else:
    sys.path.append('/usr/local/project/cdr_schemas')
    #print('CDR_SCHEMAS_DIRECTORY',os.environ['CDR_SCHEMAS_DIRECTORY'])
#sys.path.append('/usr/local/project/cdr_schemas/')
from cdr_schemas import prospectivity_models
from cdr_schemas import prospectivity_input


def process_params(req,params,post=False,post_json=False):
    r = req.GET if not post else req.POST
    if post_json:
        body = req.body.decode('utf-8')#.replace("'",'"')
        #print(body)
        r = json.loads(body)
    for param in params:
        if param in r:#.has_key(param):
            params[param] = r[param]
            #print(param,r[param])
            
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


def convertVectorToGeoJSONresponse(vector_filepath,params):
    '''
    Convert input vector file to geojson, returns json dict
    '''
    
    # Set temp path for geojson file
    sid = Path(vector_filepath).stem
    tmpgj = os.path.join('/tmp',f'{sid}.gj')

    gdal.VectorTranslate(
        tmpgj,
        vector_filepath,
        format='GeoJSON',
    )
    
    # Load the gj to a JSON var
    with open(tmpgj,'r') as f:
        gj = json.loads(f.read())
        

    # If FeatureCollection, unwrap to the first feature
    if gj['type'] == 'FeatureCollection':
        gj = gj['features'][0]
        
    
    # Get original projection
    ds = gdal.OpenEx(vector_filepath, 1)
    layer = ds.GetLayer()
    srs = layer.GetSpatialRef()
    srs.AutoIdentifyEPSG()
    s_srs = srs.GetAuthorityCode(None)
        
    # Transform to EPSG:4326 and simplify
    gj = simplify_and_transform_geojson(gj['geometry'],s_srs)
    
    #sql = f'''
        #SELECT ST_AsGeoJSON(
            #ST_Simplify(
                #ST_Transform(
                    #ST_SetSRID(
                        #ST_GeomFromGeoJSON('{str(gj['geometry']).replace("'",'"')}'),
                        #{s_srs}
                    #),
                    #4326
                #),
                #0.002 -- simplify to ~200m 
            #)
        #);
    #'''
    #gj = json.loads(reduce_geojson_precision(runSQL(sql)[0]))
    
    # Convert multi to single-part polygon
    if gj['type'] == 'MultiPolygon':
        gj['type'] = 'Polygon'
        gj['coordinates'] = gj['coordinates'][0]
    
    # Remove temp file
    os.remove(tmpgj)
    
    response = HttpResponse(
        json.dumps({
            'geojson': [gj],
            'params': params,
        })
    )
    response['Content-Type'] = 'application/json'
        
    return response
    

def simplify_and_transform_geojson(geometry,s_srs,t_srs=4326):
    '''
    geometry :  (dict) geojson dict
    s_srs :     (int) spatial reference system (PostGIS ID) of the geojson geom
    t_srs:      (int) spatial reference system (PostGIS ID) to transform to
        
    '''

    simplify = 0.002 if str(t_srs) == '4326' else 200
    sql = f'''
        SELECT ST_AsGeoJSON(
            ST_Simplify(
                ST_Transform(
                    ST_SetSRID(
                        ST_GeomFromGeoJSON('{str(geometry).replace("'",'"')}'),
                        {s_srs}
                    ),
                    {t_srs}
                ),
               {simplify} -- simplify to ~200m 
            )
        );
    '''

    # Set geojson precision to 0 if units are meters
    precision = 4
    if int(t_srs) == 102008:
        precision = 0
    
    return json.loads(reduce_geojson_precision(runSQL(sql)[0],precision=precision))
    #return json.loads(runSQL(sql)[0])
    

def convert_wkt_to_geojson(wkt_string):
    shape = wkt.loads(wkt_string)
    return mapping(shape)
    
    
def reduce_geojson_precision(data, remove_zeroes=False, precision=4):
    '''
    The gdal_polygonize process used to vectorize the rasters to geojson 
    specifies polygon coordinates to an absurd level of precision (15 decimal 
    places).
    
    This function rewrites the coordinates w/ reduced precision as an
    optimization step; it reduces file size and therefore browser load times.
    '''
    
    #print(data)
    
    # 5 gives us accuracy down to ~1m
    # see: https://en.wikipedia.org/wiki/Decimal_degrees
    #precision = 4
    
    #print(data)
    #blerg
    
    # Regex matching numbers w/ 15 decimal precision
    coords_match = re.compile(r"\d*\.\d{10}")
    coords_match2 = re.compile(r"\d*\.\d{9}")
    coords_match3 = re.compile(r"\d*\.\d{8}")

    # Regex matching "0" value entries
    dn0_match = re.compile(
        r'{ "type": "Feature", "properties": { "DN": 0 }(.*)] ] ] } }(,|)')
    
    # Regex matching invalid comma instances
    badCommas_match = re.compile(r',]')

    # Callback function for the regex matching function; reduces precision
    # of the matched object
    def mround(match):
        return "{0:.{1}f}".format(float(match.group()),precision)
    
    def remove(match):
        return ''

    def remove_badCommas(match):
        return match.group().replace(',','')

    #with open(geojson_path, 'r') as p:
        #data = p.read()

    if remove_zeroes:
        data = re.sub(dn0_match, remove, re.sub(coords_match,mround,data))
    else:
        
        data = re.sub(coords_match,mround,data)
        data = re.sub(coords_match2,mround,data)
        data = re.sub(coords_match3,mround,data)
        
    return re.sub(badCommas_match,remove_badCommas,''.join(data.split()))


# SPARQL utils from Joe Paki
def run_sparql_query(query, endpoint='https://minmod.isi.edu/sparql', values=False):
    # add prefixes
    final_query = f'''
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX : <https://minmod.isi.edu/resource/>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX gkbi: <https://geokb.wikibase.cloud/entity/>
        PREFIX gkbp: <https://geokb.wikibase.cloud/wiki/Property:>
        PREFIX gkbt: <https://geokb.wikibase.cloud/prop/direct/>
        PREFIX geo: <http://www.opengis.net/ont/geosparql#>
        \n{query}
    '''

    # send query
    response = requests.post(
        url=endpoint,
        data={'query': final_query},
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/sparql-results+json"  # Requesting JSON format
        },
        verify=False  # Set to False to bypass SSL verification as per the '-k' in curl
    )
    #print(response.text)
    try:
        qres = response.json()
        if "results" in qres and "bindings" in qres["results"]:
            df = pd.json_normalize(qres['results']['bindings'])
            if values:
                filtered_columns = df.filter(like='.value').columns
                df = df[filtered_columns]
            return df
    except:
        return None


def run_minmod_query(query, values=False):
    return run_sparql_query(
        query,
        endpoint='https://minmod.isi.edu/sparql',
        values=values
    )


def run_geokb_query(query, values=False):
    return run_sparql_query(
        query,
        endpoint='https://geokb.wikibase.cloud/query/sparql',
        values=values
    )


def get_commodity_list():
    query = '''
        SELECT ?ci ?cm ?cn
        WHERE {
            ?ci a :Commodity .
            ?ci rdfs:label ?cm .
            ?ci :name ?cn .
        } 
    '''

    return sorted(run_minmod_query(query, values=True)["cn.value"].unique())


def get_default_commodity_list():
    return [
        'Abrasive','Abrasive, Corundum', 'Abrasive, Emery', 'Abrasive, Garnet',
        'Aggregate, Light Weight','Aluminum', 'Aluminum, Contained Or Metal',
        'Aluminum, High Alumina Clay', 'Andalusite', 'Antimony', 'Arsenic',
        'Asbestos', 'Barium-Barite', 'Bismuth', 'Boron-Borates', 'Cadmium',
        'Carbon Dioxide', 'Cement Rock', 'Chromium', 'Chromium, Ferrochrome',
        'Clay', 'Clay, Ball Clay', 'Clay, Bloating Material', 'Clay, Brick',
        'Clay, Chlorite', 'Clay, Fire (Refractory)', 'Clay, Fullers Earth',
        'Clay, General', 'Clay, Glauconite', 'Clay, Hectorite', 'Clay, Kaolin',
        'Clay, Montmorillonite', 'Coal, Anthracite', 'Coal, Bituminous',
        'Coal, Lignite', 'Coal, Subbituminous', 'Cobalt', 'Copper',
        'Copper, Oxide', 'Copper, Sulfide', 'Dolomite', 'Feldspar',
        'Fluorine-Fluorite', 'Gemstone', 'Gemstone, Diamond',
        'Gemstone, Emerald', 'Gemstone, Ruby', 'Gemstone, Sapphire',
        'Gemstone, Semiprecious', 'Geothermal', 'Gold', 'Gold, Refinery',
        'Graphite', 'Graphite, Carbon', 'Gypsum-Anhydrite',
        'Gypsum-Anhydrite, Alabaster', 'Hafnium', 'Helium', 'Indium', 'Iodine',
        'Iron', 'Iron, Pig Iron', 'Iron, Pyrite', 'Kyanite', 'Lead',
        'Limestone, Dimension', 'Limestone, High Calcium',
        'Limestone, Ultra Pure', 'Lithium', 'Magnesite', 'Manganese',
        'Manganese, Ferromanganese', 'Mercury', 'Mica', 'Mineral Pigments',
        'Molybdenum', 'Natural Gas', 'Nickel', 'Niobium', 'Nitrogen-Nitrates',
        'Nonmetal', 'Potassium', 'Potassium, Alum', 'Silver',
        'Silver, Refinery', 'Tin', 'Uranium', 'Zinc', 'platinum-group elements'
    ]


def get_query_colocated_commodities(primary_commodity: str):
    print("Pri com:", primary_commodity)
    query = """
        SELECT ?si ?ri ?mn ?mi_commodity_name ?assoc_com
        WHERE {{
            ?ms a :MineralSite .
            ?ms :source_id ?si . 
            ?ms :record_id ?ri .
            ?ms :mineral_inventory ?mi .
            ?mi :commodity [ :name ?mi_commodity_name ] .
            FILTER(CONTAINS(?mi_commodity_name,  "{}"))
            ?ms :mineral_inventory ?mn .
            ?mn :commodity [ :name ?assoc_com] .
        }}
    """.format(primary_commodity)
    print("sparkutils:", query)
    return query


def get_mineral_sites(commodity: str):
    query = """
        SELECT ?ms ?msr ?mss ?mi ?loc_wkt ?crs ?com ?ore_value ?ore_grade ?grade_unit
        WHERE {{
            ?ms a :MineralSite .
            ?ms :source_id ?si . 
            ?ms :record_id ?ri .
            ?ms :location_info [ :location ?loc_wkt; :crs ?crs ] .
            ?ms :mineral_inventory ?mi .
            OPTIONAL{{?mi :ore [:ore_value ?ore_value] .}}
            OPTIONAL{{?mi :grade [:grade_value ?ore_grade; :grade_unit ?grade_unit] .}}
            ?mi :commodity [ :name ?com ] .
            FILTER contains(lcase(str(?com)), "{}")
        }}
    """.format(commodity)
    print("sparkutils:", query)
    return query


def validate_wkt_geom(wkt):
    '''
    Validates and returns a dict of parameter for the given WKT
    
    Example WKT input:
    'POLYGON((-108.1+39.4,-107.9+39.4,-107.9+39.3,-108.1+39.3,-108.0929+39.4))'
    
    '''

    wkt_string = wkt.replace('+', ' ')
    
    if 'MULTIPOLYGON' in wkt:
        if re.compile(r'^MULTIPOLYGON\(\(([\-\.\d\(\) \+,]*)\)\)$').match(wkt) == None:
            raise BadRequest('WKT Polygon format is invalid: {0}'.format(wkt))
    else:
        if re.compile(r'^POLYGON\(([\-\.\d\(\) \+,]*)\)$').match(wkt) == None:
            raise BadRequest('WKT Polygon format is invalid: {0}'.format(wkt))
    
    #wkt_string = fix_wkt_coords(wkt_string)

    return wkt_string


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


def get_processing_steps():
    processing_steps = {
        c.name: model_to_dict(c) for c in models.ProcessingStep.objects.all()
    }

    # Get processing step parameters
    for pp in models.ProcessingStepParameter.objects.select_related('processingstep').all():
        psname = pp.processingstep.name

        # Add step if not included yet
        if 'parameters' not in processing_steps[psname]:
            processing_steps[psname]['parameters'] = {}
            processing_steps[psname]['parameter_defaults'] = {}
            
        load_parameters(processing_steps[psname]['parameters'],pp)
        
        # Add convenience var w/ default vals for each parameter
        processing_steps[psname]['parameter_defaults'][pp.name] = pp.html_attributes['value']
        
    
    return processing_steps

def create_fishnet(
        resolution,
        fishnet_srid,
        clip_polygon_wkt,
    ):
    '''
        resolution: float (spatial resolution in units of the provided SRID)
        fishnet_srid: int (SRID id as indicated in the CRS model)
        clip_polygon_wkt: already validated WKT string
    '''
    
    
    (xmin, xmax, ymin, ymax) = runSQL(
        f'''
            SELECT ST_XMin(a.geom), ST_XMax(a.geom), ST_YMin(a.geom), ST_YMax(a.geom)
            FROM (
                SELECT(ST_Transform(
                    ST_GeomFromText('{clip_polygon_wkt}',4326),
                    {fishnet_srid}
                )) as geom
            ) a
        ''')

    resolution = float(resolution)

    # get rows/columns
    rows = math.ceil((ymax - ymin) / resolution)
    cols = math.ceil((xmax - xmin) / resolution)
    print(rows + cols)
    if rows + cols > 500:
        return {'message': 'Resolution too high to produce a grid preview'}

    mls = 'MULTILINESTRING('

    # create grid lines
    for i in range(cols+1):
        line = ogr.Geometry(ogr.wkbLineString)
        px = xmin + (i * resolution)
        mls += f'({px} {ymin}, {px} {ymax+resolution}),'

    for j in range(rows+1):
        line = ogr.Geometry(ogr.wkbLineString)
        py = ymin + (j * resolution)
        mls += f'({xmin} {py}, {xmax+resolution} {py}),'

    mls = mls.rstrip(',')
    mls += ')'
    
    sql = f'''
        SELECT ST_AsGeoJSON(ST_Intersection(
            ST_Transform(
                ST_GeomFromText('{mls}',{fishnet_srid}),
                4326
            ),
            ST_GeomFromText('{clip_polygon_wkt}',4326)
        ))
    '''

    return runSQL(sql)[0]

    
def runSQL(sql):
    '''
    Run raw SQL query, returning just the first row
    '''
    with connection.cursor() as cursor:
        cursor.execute(sql)
        res = cursor.fetchone()
        
    return res
        
        
def get_tif_srs(ds):
    '''
    ds : Python gdal dataset object (i.e. what you get from: ds = gdal.Open(tif_path))
    '''
    prj = ds.GetProjection()
    srs = osr.SpatialReference(prj.title())
    
    return srs

def get_tif_resolution(tif_path):
    td = None
    if ' ' in tif_path:
        td = tempfile.TemporaryDirectory()
        url = tif_path.replace("/vsicurl_streaming/","")
        os.system(f'wget -P {td.name} "{url}"')
        print(td, os.path.basename(tif_path))
        ds = gdal.Open(os.path.join(td.name,os.path.basename(tif_path)))
    else:
        ds = gdal.Open(tif_path)
    
   # ds = gdal.Open(tif_path)
    _, xres, _, _, _, yres  = ds.GetGeoTransform()
    srs = get_tif_srs(ds)
    #prj = ds.GetProjection()
    #srs = osr.SpatialReference(prj.title())
    units = srs.GetLinearUnitsName()

    # If units are in degrees, do a rough approximation of
    # resolution in meters w/ assumption that 1 degree ~= 100km
    # Some projections appear incorrectly set too, so if resolution is
    # less than 1, we assume degrees
    if (units in ('degrees','Degrees','degree','Degree')) or xres < 1:
        xres *= 100000
    
    del ds
    if td:
        td.cleanup()
    
    return xres


def sync_cdr_prospectivity_datasources_to_datalayer(
        data_source_id=None,
        update_all=False
    ):
    '''
    data_source_id: (optional) filter by data source ID if needed
    update_all:     if False, only absent layers will be added; if True, all 
                    attributes of all layers will be updated
    '''
    
    ### Pull layers from CDR
    cdr = cdr_utils.CDR()
    res = cdr.get_prospectivity_data_sources()

    ### Pull dsids from the GUI DB
    existing_dsids = [
        x[0] for x in 
        models.DataLayer.objects.all().values_list('data_source_id')
    ]

    for ds in res:

        if data_source_id and ds['data_source_id'] != data_source_id:
            continue
        
        if not update_all and ds['data_source_id'] in existing_dsids:
            continue
        
        if 'user_upload_example' in ds['data_source_id']:
            #print(ds)
            continue
    
        if ds['evidence_layer_raster_prefix'] in (
            '12mhack_upload_20241031_vector',
            '12mhack_upload_20241031_vectest_c',
            ):
            continue
    
        #if '12a66407aa9e4941a7d67e23c404e357.tif' in ds['download_url']:
        #    continue
        
        if True: #ds['format'] == 'tif':
            #ds = r#['data_source']

            #print(r)
            #blerg

            #name = ds['description'].replace(' ','_').replace('-','_').replace('(','').replace(')','')
            name = ds['data_source_id']

            dl, created = models.DataLayer.objects.get_or_create(
                data_source_id = ds['data_source_id'],
                defaults = {
                    'name' : ds['evidence_layer_raster_prefix'],
                    'name_alt': ds['description'],
                    'description': ds['description'],
                    'authors': ds['authors'],
                    'data_format': ds['format'],
                    'publication_date': ds['publication_date'],
                    'doi': ds['DOI'],
                    'datatype': ds['type'],
                    'category': ds['category'].capitalize(),
                    'subcategory': ds['subcategory'].capitalize().rstrip('s'),
                    'spatial_resolution_m': ds['resolution'][0],
                    'download_url': ds['download_url'],
                    'reference_url': ds['reference_url'],
                    'derivative_ops': ds['derivative_ops']
                },
            )
        else:
            print('NONTIF:',ds)
            

def load_new_layers(
        dsids=None,
        cma_id=None,
        event_id=None,
        include_outputlayers=True,
        include_processedlayers=False
    ):
    dls = {'datalayers_lookup': {}}
    
    # NOTE: commenting this filter out for now since we're no longer grabbing
    #       model outputs by default on get_metadata
    #if dsids:
    dls = get_datalayers_for_gui(
        data_source_ids=dsids,
        include_datalayers=False,
        include_outputlayers=include_outputlayers,
        include_processedlayers=include_processedlayers,
        cma_id=cma_id,
        event_id=event_id
    )#data_source_ids = dsids)
        
    return dls['datalayers_lookup']


def sync_cdr_prospectivity_processed_layers_to_datalayer(
        layer_id=None,
        cma_id=None,
        event_ids=[],
        sync_remote_to_local=True, # <- downloads files to local disk to speed rendering
        update_all=False,
    ):
    '''
    data_source_id: (optional) filter by data source ID if needed
    '''
    
    ### Pull dsids from the GUI DB
    existing_dsids = [
        x[0] for x in 
        models.ProcessedLayer.objects.all().values_list('data_source_id')
    ]
    
    datalayer_subcategories = {
        x.data_source_id: x for x in 
        models.DataLayer.objects.all()
    }
    
    ### Pull layers from CDR
    cdr = cdr_utils.CDR()
    
   # if cma_id:
    event_ids = cdr.get_processed_data_layer_events()
    cmas_ids = [cma['cma_id'] for cma in cdr.get_cmas()]
        
    dsids = []
    #for event_id in event_ids:
    for cma_id in cmas_ids:
        res = cdr.get_processed_data_layers(cma_id=cma_id)

        for i,ds in enumerate(res):
            #print(ds)
            if 'title' in ds and 'testing' in ds['title']:
                continue
            
            if layer_id and ds['layer_id'] != layer_id:
                continue
            
            if not update_all and ds['layer_id'] in existing_dsids:
                continue
            
            if ds['download_url'].split('.')[-1] != 'tif':
                continue
            
            if cma_id and ds['cma_id'] != cma_id:
                continue
        
            if event_ids and ds['event_id'] not in event_ids:
                continue

            print(i, 'get/creating:',ds['layer_id'])
            #continue
            stats_minimum = None
            stats_maximum = None
            #print(ds)
            datalayer = None
            category = 'Training'
            subcategory = 'Label rasters'

            # Try to pull category/subcategory info from the original datasource
            if not ds['label_raster']:
                print(ds)
                if ds['data_source_id']:
                    datalayer = datalayer_subcategories[ds['data_source_id']]
                    subcategory = datalayer.subcategory
                    category = datalayer.category
                else:
                    subcategory = 'Features'
                    category = 'Geology'
            dl, created = models.ProcessedLayer.objects.get_or_create(
                data_source_id = ds['layer_id'],
                #download_url = ds['download_url'],
                defaults = {
                    'name' : ds['title'],
                    'name_alt': ds['title'],
                    'description': ds['title'],
                    'data_format': 'tif',
                    'category': category,
                    'subcategory': subcategory,#ds['model'].capitalize().rstrip('s'),
                    'download_url': ds['download_url'],
                    'system': ds['system'],
                    'system_version': ds['system_version'],
                    'cma_id': ds['cma_id'],
                    'event_id': ds['event_id'],
                    'transform_methods': ds['transform_methods'],
                    'datalayer': datalayer,
                    'label_raster': ds['label_raster'],
                },
            )
            if created:
                print('\tcreated!')
                dsids.append(dl.data_source_id)
        #else:
        #    print('NONTIF:',ds)
        
    if len(dsids) > 0:
        print('New processed layers; processing...')
        if sync_remote_to_local:
            sync_remote_outputs_to_local(do_processed_layers=True)
            
        # Finally, rewrite mapfile
        print('Rewriting mapfile')
        mapfile.write_mapfile()
    
    return dsids


def sync_cdr_prospectivity_outputs_to_outputlayer(
        layer_id=None,
        cma_id=None,
        sync_remote_to_local=True, # <- downloads files to local disk to speed rendering
        update_all=False,
    ):
    '''
    data_source_id: (optional) filter by data source ID if needed
    '''
    
    ### Pull layers from CDR
    cdr = cdr_utils.CDR()
    res = cdr.get_prospectivity_output_layers()

    ### Pull dsids from the GUI DB
    existing_dsids = [
        x[0] for x in 
        models.DataLayer.objects.all().values_list('data_source_id')
    ]

    dsids = []
    for i,ds in enumerate(res):
        #print(ds)
        if layer_id and ds['layer_id'] != layer_id:
            continue
        
        if not update_all and ds['layer_id'] in existing_dsids:
            continue
        
        #if ds['download_url'].split('.')[-1] != 'tif':
        #    continue
        
        if cma_id and ds['cma_id'] != cma_id:
            continue
        ext = ds['download_url'].split('.')[-1] 

        print(i, 'get/creating:',ds['layer_id'])
        #continue
        stats_minimum = None
        stats_maximum = None
        if 'ikelihoo' in ds['title']:
            stats_minimum = 0
            stats_maximum = 1
            
        dl, created = models.OutputLayer.objects.get_or_create(
            data_source_id = ds['layer_id'],
            #download_url = ds['download_url'],
            defaults = {
                'name' : ds['title'],
                'name_alt': ds['title'],
                'description': ds['title'],
                #'authors': ds['authors'],
                #'data_format': ds['format'],
                #'publication_date': ds['publication_date'],
                #'doi': ds['DOI'],
                #'datatype': ds['type'],
                'data_format': ext,
                'category': 'model outputs',
                'subcategory': ds['model'].capitalize().rstrip('s'),
                #'spatial_resolution_m': ds['resolution'][0],
                'download_url': ds['download_url'],
                #'reference_url': ds['reference_url'],
                #'derivative_ops': ds['derivative_ops']
                'system': ds['system'],
                'system_version': ds['system_version'],
                'model': ds['model'],
                'model_version': ds['model_version'],
                'output_type': ds['output_type'],
                'cma_id': ds['cma_id'],
                'model_run_id': ds['model_run_id'],
                'stats_minimum': stats_minimum,
                'stats_maximum': stats_maximum,
            },
        )
        if created:
            print('\tcreated!')
            dsids.append(dl.data_source_id)
        #else:
        #    print('NONTIF:',ds)
        
    if len(dsids) > 0:
        print('New output layers; processing...')
        if sync_remote_to_local:
            sync_remote_outputs_to_local()
            
        # Finally, rewrite mapfile
        print('Rewriting mapfile')
        mapfile.write_mapfile()
    
    return dsids
            
            
def getOutputLayers(do_processed_layers=False):
    obj = models.OutputLayer if not do_processed_layers else models.ProcessedLayer
    return obj.objects.all().order_by('category','subcategory','name')


def get_output_layer_local_sync_path(dsid,ext='tif'):
    dd = f'/net/{settings.MAPSERVER_SERVER}{settings.TILESERVER_LOCAL_SYNC_FOLDER}'
    
    return os.path.join(dd,f'{dsid}.{ext}')


def sync_remote_outputs_to_local(dsid=None,do_processed_layers=False):
    #dd = f'/net/{settings.MAPSERVER_SERVER}{settings.TILESERVER_LOCAL_SYNC_FOLDER}'

    # for datalayer in dm_util.getDataLayers():
    for datalayer in getOutputLayers(do_processed_layers=do_processed_layers):
        #print(datalayer.download_url)

        if dsid and datalayer.data_source_id != dsid:
            continue
        
        ext = datalayer.download_url.split('.')[-1]

        #ofile = os.path.join(dd,f'{datalayer.data_source_id}.tif')
        ofile = get_output_layer_local_sync_path(datalayer.data_source_id,ext=ext)
        if not os.path.exists(ofile):
            print('syncing to local:',datalayer.download_url)
            bn = os.path.basename(datalayer.download_url)
            with requests.get(datalayer.download_url) as r:
                with open(ofile,'wb') as f:
                    #print(r.content)
                    f.write(r.content)

            # Do extra stuff for rasters
            if  datalayer.data_format == 'tif':
                # Compress and add overviews
                temp_tif = 'temp_compress.tif'
                cmd = f'gdal_translate -co "COMPRESS=LZW" -co "BIGTIFF=YES" {ofile} {temp_tif}'
                os.system(cmd)
                shutil.move(temp_tif, ofile)

                os.system(f'gdaladdo {ofile} 2 4 8 16')

    
def get_datalayers_for_gui(
        data_source_ids=[],
        include_datalayers=True,
        include_outputlayers=True,
        include_processedlayers=True,
        cma_id=None,
        event_id=None,
    ):
    datalayers = {'User uploads':{}} # this object sorts by category/subcategory
    datalayers_lookup = {} # this object just stores a lookup by 'name'
    filters = {'disabled': False}
    if data_source_ids:
        filters['data_source_id__in'] = data_source_ids
    if cma_id:
        filters['cma_id'] = cma_id
    if event_id:
        filters['event_id'] = event_id

    mods = []
    if include_datalayers:
        mods.append(models.DataLayer)
    if include_outputlayers:
        mods.append(models.OutputLayer)
    if include_processedlayers:
        mods.append(models.ProcessedLayer)
    #print(filters, mods)
    for Obj in mods:#(models.DataLayer, models.OutputLayer):
        for d in Obj.objects.filter(**filters).order_by(
                'category','subcategory','name'
            ):
            
            if ('12m_hack' in d.description or 
                '12mhack' in d.description or 
                '20240905' in d.description or 
                'tdk' in d.description or
                'tdw' in d.description or
                d.name in ('jane_test_upload2',)
                ): #or 'cma-lithium-' in d.description:
                continue
            
            cat = d.category if d.subcategory != 'User upload' else 'User uploads'
            subcat = d.subcategory if d.subcategory != 'User upload' else d.category
            
            if cat not in datalayers:
                datalayers[cat] = {}
            if subcat not in datalayers[cat]:
                datalayers[cat][subcat] = []
                
            data = model_to_dict(d)
            if 'publication_date' in data:
                data['publication_date'] = str(data['publication_date'])[:-9]
            name_pretty = d.name
            if d.name_alt:
                name_pretty = d.name_alt if ': ' not in d.name_alt else d.name_alt.split(': ')[1]
            if data['extent_geom'] is not None and data['extent_geom'].empty:
                data['extent_geom'] = None
            if data['extent_geom']:
          
                data['extent_geom'] = data['extent_geom'].json
    
            if 'b4050056d38a449fa3d940008e277145' in data['download_url']:
                data['extent_geom'] = '{ "type": "Polygon", "coordinates": [[[-180,86.3], [-180,16.8], [-12.1,16.8], [-12.1,86.3], [-180,86.3]]]}'
    
            
            if 'datalayer' in data and data['datalayer']:
                data['data_source_id_orig'] = d.datalayer.data_source_id
                del data['datalayer']
                
            
            data['gui_model'] = str(Obj._meta).split('.')[1]
            #print(data['extent_geom'], data['extent_geom'])
            data['name_pretty'] = name_pretty
            datalayers[cat][subcat].append(data)
            datalayers_lookup[d.data_source_id] = data
            
        
    return {
        'datalayers': datalayers,
        'datalayers_lookup': datalayers_lookup,
    }


# https://guide.cloudnativegeo.org/cloud-optimized-geotiffs/writing-cogs-in-python.html
def cogify_from_buffer(data):
    """
    Given the path to a TIF file, turn it into a cloud optimized geotiff (COG).
    If the given COG already exists, it will be overwritten.

    Parameters
    ----------
    data : str
        Memory data

    Returns
    -------
    cog_filename : str
        File path to the COG that was created and/or overwritten.
    """
    
    #cog_filename = '/home/mgbillmi/PROCESSING/cogify_test.tif'
    
    #with open(cog_filename,'wb') as f:
    #    f.write(data)
    
    #output_memfile = MemoryFile()
    td = tempfile.TemporaryDirectory()
    output_memfile = os.path.join(
        #settings.BASE_DIR,
        #'cma',
        #'temp',
        td.name,
        f'{getUniqueID()}.tif'
    )
    
    print('temp file:',output_memfile)
    with MemoryFile(data).open() as memfile:
        dst_profile = cog_profiles.get("deflate")

        # Creating destination COG
        cog_translate(
            memfile,
            output_memfile,#.name,
            dst_profile,
            use_cog_driver=True,
            in_memory=False,
            #web_optimized=True,
            overview_resampling="cubic"
        )

    return open(output_memfile,'rb')

def process_cma(cma):
    #print(cma)
    # Reproject to WGS84
    cma['extent'] = simplify_and_transform_geojson(
        cma['extent'],
        cma['crs'].split(':')[1],
    )
    
    return cma

def get_array_shape_from_bounds_and_res(bounds: np.ndarray, pixel_size: Number):

    # upack the bounding box
    coord_west, coord_south, coord_east, coord_north = bounds[0], bounds[1], bounds[2], bounds[3]

    # Need to get the array shape from resolution
    raster_width = math.ceil(abs(coord_west - coord_east) / pixel_size)
    raster_height = math.ceil(abs(coord_north - coord_south) / pixel_size)

    return raster_width, raster_height, coord_west, coord_north


def create_template_raster_from_bounds_and_resolution(
        bounds,
        target_crs,
        pixel_size,
        clipping_gdf
    ):
    #print('bounds',bounds)
    #print('pixel size',pixel_size)

    raster_width, raster_height, coord_west, coord_north = get_array_shape_from_bounds_and_res(
        bounds,
        pixel_size
    )
    out_array = np.full((1, raster_height, raster_width), 0, dtype=np.float32)

    out_transform = from_origin(coord_west, coord_north, pixel_size, pixel_size)
    # TODO: Figure out how to make the clipping gdf and if it is a geodataframe, then if indent the next three lines
    # This should really only get done if the polygon != bounds
    shapes = ((geom) for geom in clipping_gdf.geometry)
    # This fill parameter doesn't seem to be working as I expect
    # masking_array = rasterize(shapes=shapes, fill=np.finfo('float32').min, out=out_array, transform=out_transform, default_value=1)
    masking_array = rasterize(
        shapes=shapes,
        fill=np.finfo('float32').min,
        out=out_array,
        transform=out_transform,
        default_value=1
    )
    
    out_array = np.where(
        masking_array == 1, 1, np.finfo('float32').min
    ).astype(np.float32)

    out_meta = {
        "width": raster_width,
        "height": raster_height,
        "count": 1,
        "dtype": out_array.dtype,
        "crs": target_crs,
        "transform": out_transform,
        "nodata": np.finfo('float32').min,
        "driver": 'GTiff',
        'compress': 'lzw',
    }

    # Replace with S3 boto3 type stuff here
    #mem_file = MemoryFile()
    tmpfile = os.path.join(settings.BASE_DIR,'cma','temp',f'{getUniqueID()}.tif')#tempfile.NamedTemporaryFile()
    with rio.open(tmpfile, 'w', **out_meta) as ds:
    #with tmpfile.open(**out_meta) as ds:
        ds.write(out_array)
    
    #with rio.open('/home/mgbillmi/PROCESSING/StatMAGIC/test_template.tif', 'w', **out_meta) as new_dataset:
        #new_dataset.write(out_array)
        
    return tmpfile


def build_template_raster_from_CMA(cma, proj4, buffer_distance=0):
    
    geom = cma.extent.coordinates#['extent']['coordinates']
    poly = geometry.Polygon(geom[0][0])
    #print(geom)
    #try:
        #target_crs = CRS.from_epsg(cma.crs)
    #except rio.errors.CRSError:
    target_crs = CRS.from_string(proj4)

    clipping_gdf = gpd.GeoDataFrame(geometry=[poly], crs=target_crs)
   # clipping_gdf = clipping_gdf.to_crs(target_crs)
    if buffer_distance > 0:
        clipping_gdf.geometry = clipping_gdf.buffer(buffer_distance)
    bounds = clipping_gdf.total_bounds

    # Todo: update create function to use both dimensions
    pixel_size = cma.resolution[0]

    return create_template_raster_from_bounds_and_resolution(
        bounds=bounds,
        target_crs=target_crs,
        pixel_size=pixel_size,
        clipping_gdf=clipping_gdf
    )

def get_cache_key(prefix,params,exclude_params=[]):
    k = [prefix,]#str(settings.VERSION)]
    for p in sorted(params):
        if p not in exclude_params and p not in (
           #'wkt',
            #'wkt_geos',
            'limit',
            'ignore_cache',
            #'output_spatial_aggregations',
            #'output_temporal_aggregations',
            #'nawfd_stochastic_use_cached',
            'format',
            #'format_for_calculator',
            'ignore_limit',
            ):
            #v = params[p] if params[p] else '|'
            v = str(params[p]).replace(' ','') if params[p] not in (None,'None') else ''
            if p in ('bbox_polygon',):
                v = v.replace('"type":"Polygon","coordinates":','').replace('{','').replace('}','').replace('[','').replace(']','')[:150]
            k.append(v)
    
    return '|'.join(k)


def downloadVector(FeatureCollection, base_name='test5', output_format='shp'):
    '''
    Data is a list of GeoJSON features; a dict w/ 'features'
    '''
    
    format_map = {
        'shp': {
            'extension': 'zip',
            'driver_name': 'ESRI Shapefile',
        }, 
        'gpkg': {
            'extension': 'gpkg',
            'driver_name': 'GPKG',
            'mime': 'application/geopackage+sqlite3'
        },
        'geojson': {
            'extension': 'geojson',
            'driver_name': 'GeoJSON',
            'mime': 'application/geo+json'
        },
    }
    
    # map of fields to be truncated b/c the way shapefile does this
    # automatically kind of sucks
    trunc_fields = {
        'mineral_site_ids': 'minsiteids',
        'tonnage_unit': 'tonn_unit',
        'top1_deposit_type': 't1_deptype',
        'top1_deposit_group': 't1_depgrp',
        'top1_deposit_environment': 't1_depenv',
        'top1_deposit_classification_confidence': 't1_depconf',
        'top1_deposit_classification_source': 't1_depsrc',
        'centroid_epsg_4326': 'cntrd_4326',
        'contained_metal': 'cont_metal',
        'contained_metal_unit': 'cont_mt_un'
    }

    fobj = format_map[output_format]
    print(output_format, fobj)

    ext = fobj['extension']
    unid = getUniqueID()
    shp_tempfile = os.path.join('/tmp', f'{base_name}_{unid}.{output_format}')


    # "4" = ESRI Shapefile
    #driver = ogr.GetDriver(6)
    driver = ogr.GetDriverByName(fobj['driver_name'])

    ds = driver.CreateDataSource(shp_tempfile)

    # Create spatial reference
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    # Create the layer
    layer = ds.CreateLayer('layer', srs, geom_type=ogr.wkbPoint)

    # Add fields; pull from properties
    type_dict = {
        str: ogr.OFTString,
        #type(u''): ogr.OFTString,
        float: ogr.OFTReal,
        int: ogr.OFTInteger,
        np.float64: ogr.OFTReal,
        list: None,#ogr.OFTString,
        dict: None,#ogr.OFTString
    }
    
    data = FeatureCollection['features']
    if data:
        
        fields = data[0]['properties'].keys()
        for field in fields:
            fn = field
            if output_format == 'shp':
                fn = field if field not in trunc_fields else trunc_fields[field]
                
            v = data[0]['properties'][field]
            dtype = ogr.OFTString  # assume string by default
            if v:
                dtype = type_dict[type(v)]
            if not dtype:
                continue
            
            layer.CreateField(ogr.FieldDefn(str(fn), dtype))


        # Now add data
        #print(len(data))
        for row in data:
            feature = ogr.Feature(layer.GetLayerDefn())
            for p, v in row['properties'].items():
                p2 = p
                if output_format == 'shp':
                    p2 = p if p not in trunc_fields else trunc_fields[p]
                u = v
                if v:
                    dtype = type_dict[type(v)]
                if not dtype:
                    continue
    
                feature.SetField(str(p2), u)

            #if row['geometry']['type'] == 'GeometryCollection':
                #for point in row['geometry']['geometries']:
                    #point = ogr.CreateGeometryFromJson(json.dumps(point))
                    #feature.SetGeometry(point)
                    #layer.CreateFeature(feature)
                    
            #else:
            #point = ogr.CreateGeometryFromJson(json.dumps(row['geometry']))
            point = ogr.CreateGeometryFromJson(json.dumps(row['geometry']))
            feature.SetGeometry(point)
            layer.CreateFeature(feature)

            feature = None
            poly = None

        ds = None
        
    # Now write the files to zip
    if output_format == 'shp':
        print(shp_tempfile)
        bytes_io = BytesIO()
        with zipfile.ZipFile(bytes_io, 'w', zipfile.ZIP_DEFLATED) as archive:
            for ext in ('.shp','.dbf','.shx','.prj'):
                f = shp_tempfile.replace('.shp',ext)
                archive.write(f,os.path.basename(f))

        bytes_io.seek(0) # Go to the first byte
        response = HttpResponse(bytes_io.read(), content_type='application/zip')
        bytes_io.close() # Dispose of the in-memory file

        
        
    else:
         response = HttpResponse(
            open(shp_tempfile,'rb'),
            content_type=fobj['mime']
         )
         
    response['Content-Disposition'] = f'attachment; filename="{base_name}_{unid}.{fobj["extension"]}'
    
    return response


def get_extent_geom_of_raster(tif):
    '''
    tif : (str) path to geotiff
    
    returns : (dict) geojson spec
    
    '''
    
    xds = xarray.open_dataarray(tif,engine='rasterio')
    coords = []
    if xds.rio.crs:
        transform_bounds_box = box(*xds.rio.transform_bounds("EPSG:4326"))

        # Loop through coords and change any large longitudes (~W of Alaska) to 
        # -180 so that the geometry does not draw the wrong way around the world
        xx, yy = transform_bounds_box.exterior.coords.xy

        for i,x in enumerate(xx):
            x0 = x if x < 160 else -180
            coords.append([x0,yy[i]])
        
    else:
        print('No valid CRS for file: ',tif)
    
    return {
        'type': 'Polygon',
        'coordinates': [coords]
    }

def process_vector_for_mapfile(dataset):
    '''
        dataset: models.DisplayLayer instance (OutputLayer or DataLayer)
    '''
    
    # Get datasource ID from the download URL
    #dsid = Path(dataset.download_url).stem
    dsid = dataset.data_source_id
    
    # Check if already downloaded
    path_base = get_output_layer_local_sync_path(dsid,ext='')
    if len(glob.glob(f'{path_base}*')) == 0:
        print('downloading to local sync dir:',dataset.download_url)
    
        # If not, download the file
        resp = urlopen(dataset.download_url)
        
        # Open zipfile
        try:
            myzip = zipfile.ZipFile(BytesIO(resp.read()))
        except:
            print(f'Problem opening zipfile: date_source_id={dsid}; download_url={dataset.download_url}')
            return
        
        # Extract contents to temporary directory
        with tempfile.TemporaryDirectory() as tempdir:
            myzip.extractall(tempdir)
            
            # Now find the dir w/ the .shp and move all those files to the local
            # sync folder 
            
            # Identify the dir with the shapes
            #td = glob.glob(f'{tempdir}/*')[0]
            #for f in glob.glob(f'{td}/*'):
            for root, dirs, files in os.walk(tempdir):
                for f in files:
                    #print(root,dirs,f)
                    # Extract local sync path
                    stem = Path(f).stem
                    exts = f.split('/')[-1].split(stem)[1].lstrip('.')
                    sync_path = get_output_layer_local_sync_path(dsid,ext=exts)
                    
                    # Copy to local sync dir
                    print(f"\tsyncing {f} to: {sync_path}")
                    shutil.move(os.path.join(root,f), sync_path)
                    
                    # Run shptree to index the file
                    if exts == 'shp':
                        print("\tindexing vector...")
                        os.system('shptree {sync_path}')
                    

    # vvv NOTE: abandoning this b/c mpm_input_preprocessing 
    #     module already handles these
    # Pre-process the features into geojson for more efficient submission of 
    # preprocessing jobs
    gdf = None
    #features_file = get_output_layer_local_sync_path(dsid,ext='features')
    #if not os.path.exists(features_file):
        #gdf = gpd.read_file(features_file.replace('.features','.shp'))
        #gdfjson = reduce_geojson_precision(
                #gdf.to_json(), 
                #precision=4
        #)
        #gdfjson = json.loads(gdfjson)
        #features_data = []
        #for f in gdfjson['features']:
            #features_data.append(f['geometry'])
        
        #with open(features_file,'w') as f:
            #f.write(json.dumps(features_data))

    # If missing metadata, get:
    if (dataset.extent_geom is None or 
        dataset.attribute_stats is None or 
        dataset.vector_format is None):

        # Open shapefile 
        shp = f'{path_base}shp'
        print('extracting metadata for:',shp)
        if not gdf:
            gdf = gpd.read_file(shp)
        
        if dataset.vector_format is None:
            # NOTE: Assuming here that the type of first feature represents the 
            #       type of ALL features, which may not be the case
            gt = gdf.geom_type[0].upper()
            if gt == 'LINESTRING':
                gt = 'LINE'
            dataset.vector_format = gt 
        
        if dataset.attribute_stats is None:
        
            # Get attribute stats
            stats = {}
            for colname in gdf.columns:
                if colname in ('geometry',):
                    continue
                
                #print(colname)
                dtype = gdf.dtypes[colname]
                s = {}
                if dtype in ('float','float64','int','int64'):
                    s = {
                        'min': float(gdf[colname].min()),
                        'max': float(gdf[colname].max())
                    }
                if dtype in ('datetime',):
                    s = {
                        'min': gdf[colname].min(),
                        'max': gdf[colname].max()
                    }
                if dtype in ('string','object'):
                    s = {
                        'unique_values': list(gdf[colname].unique())
                    }
                stats[colname] = s
                #print(colname,dtype)
            #print(dtype,stats)
            dataset.attribute_stats = stats
            
        if dataset.extent_geom is None:
            # Get bounds
            [xmin,ymin,xmax,ymax] = gdf.to_crs(4326).total_bounds
            coords = [
                [xmin,ymin],
                [xmin,ymax],
                [xmax,ymax],
                [xmax,ymin],
                [xmin,ymin]
            ]
            gj = json.dumps({
                'type': 'Polygon',
                'coordinates': [coords]
            })
            geom = GEOSGeometry(gj)

            dataset.extent_geom = geom#GEOSGeometry(gj)
            
        dataset.save()
    
    
    

def download_urls_to_zip(urls_to_download, zipname):
    from zipfile import ZipFile, ZIP_DEFLATED
    from io import BytesIO, StringIO
    import requests

    # Now write the files to zip
    bytes_io = BytesIO()

    with ZipFile(bytes_io, 'w', ZIP_DEFLATED) as archive:
        for url in urls_to_download:
            print(url)
            print(os.path.basename(url))
            file_contents = requests.get(url).content
            archive.writestr(os.path.basename(url), file_contents)
            # archive.write(file_contents, os.path.basename(url))

    bytes_io.seek(0)
    response = HttpResponse(bytes_io.read(), content_type='application/zip')
    bytes_io.close()
    print(zipname)
    response['Content-Disposition'] = f'attachment; filename="{zipname}"'

    return response
    
    
def clean_line(line):
    #print(str(line))
    return line.replace('\n','').replace('\r','').replace('"','').split(',')
    
def process_transform_methods(transform_methods,processing_steps):
    #  This list can be:
    #    * any length
    #    * any combination/order of processing types in:
    #       https://github.com/DARPA-CRITICALMAAS/cdr_schemas/blob/main/cdr_schemas/prospectivity_input.py#L95
    #
    #  But, FWIW wouldn't work if multiple transform methods have a 
    #  identical specifications (e.g. if both transform and scaling had
    #  'mean' option, that would confuse things)
    
    tms = []
    for tm in transform_methods:
        # Skipping 'scale' b/c there are no schema definitions for the min/max values
        if tm['name'] == 'scale':
            continue
        
        if tm['name'] not in ('impute',):
            dfs = processing_steps[tm['name']]['parameter_defaults']
            vs = {}
            for p,default_v in dfs.items():
                v = default_v
                if p in tm['parameters']:
                    v = tm['parameters'][p]
                vs[p] = v
                tms.append(v)
            
        if tm['name'] == 'impute':
            dfs = processing_steps[tm['name']]['parameter_defaults']
            vs = {}
            for p,default_v in dfs.items():
                v = default_v
                if p in tm['parameters']:
                    v = tm['parameters'][p]
                vs[p] = v
                
            v = prospectivity_input.Impute(
                impute_method=vs['method'],
                window_size=[vs['window_size']]*2
            )

            tms.append(v)
            
    return tms

    ## Open raster, pull out metadata and data
   ## ds = gdal.Open(tif)

    #band1 = ds.GetRasterBand(1)
    #rows = ds.RasterYSize
    #cols = ds.RasterXSize
    #gt = ds.GetGeoTransform()
    #nodata = band1.GetNoDataValue()
    #srs = get_tif_srs(ds)
    
    ## If no SRS, just send back a polygon w/ the extent
    ##if not srs.GetAuthorityCode(None):
    #minx = gt[0]
    #maxy = gt[3]
    #maxx = minx + gt[1] * ds.RasterXSize
    #miny = maxy + gt[5] * ds.RasterYSize
    ##print [minx, miny, maxx, maxy]

    #del ds
    
    #geom = ogr.CreateGeometryFromJson(json.dumps({
        #'type': 'Polygon',
        #'coordinates': [[
            #[minx,miny],
            #[minx,maxy],
            #[maxx,maxy],
            #[maxx,miny],
            #[minx,miny]
        #]]
    #}))
    #t_srs = osr.SpatialReference()
    #t_srs.ImportFromEPSG(4326)
    #transform = osr.CoordinateTransformation(
        #srs,
        #t_srs
    #)
    #geom.Transform(transform)
    
    #return json.loads(geom.ExportToJson())

    # NOTE: The code below was trying to create an extent for the raster that
    #       delineated the boundary of non-nodata pixels. This works okay for 
    #       some data layers, but for many, the process either (a) failed, or 
    #       (b) took 24 hours+ to process. So that's why we're defaulting to
    #       just showing the BBOX only as coded above.

    #arr = band1.ReadAsArray(0, 0, cols, rows)

    ## Create in-memory version that is reclassified to binary
    #driver = gdal.GetDriverByName('MEM')
    #ds_reclass = driver.Create('', cols, rows, 1, band1.DataType)

    ## Set metadata on the temp file
    #ds_reclass.SetGeoTransform(gt)
    #ds_reclass.SetProjection(ds.GetProjection())
    #band_reclass = ds_reclass.GetRasterBand(1)
    #band_reclass.SetNoDataValue(0)
    #outData = np.copy(arr)

    ## Reclassify so that everything that is not nodata = 1
    #outData[arr!=nodata] = 1
    #outData[arr==nodata] = 0

    ## Write reclassed data
    #band_reclass.WriteArray(outData,0,0)
    #band_reclass.FlushCache()

    #del ds
    #del outData

    ## Now convert to vector
    #drv = ogr.GetDriverByName("Memory")
    #shp = f'/vsimem/cvshp_{getUniqueID()}.shp'
    #dst_ds = drv.CreateDataSource(shp)
    #dst_layer = dst_ds.CreateLayer(shp, srs=srs)

    #gdal.Polygonize(band_reclass,band_reclass, dst_layer, -1)


    ## Finally, simplify/transform and convert to geojson
    ## For these brief visualization extents, set to a pretty coarse simplification
    ## level: 5km
    #simplify_prec = 0.05 if srs.GetAuthorityCode(None) in ('4269','4326','3857') else 5000

    #multi = ogr.Geometry(ogr.wkbMultiPolygon)
    #for feature in dst_layer:
        #geom = feature.geometry().Simplify(simplify_prec)
        #multi.AddGeometry(geom)

    #t_srs = osr.SpatialReference()
    #t_srs.ImportFromEPSG(4326)
    #transform = osr.CoordinateTransformation(
        #srs,
        #t_srs
    #)
    #multi.Transform(transform)
    #multi.FlattenTo2D()
    #gj = json.loads(multi.UnionCascaded().ExportToJson())
    
    #return gj
