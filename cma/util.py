'''
Backend utility code.
'''

import json, math, os, random, re, requests, string, tempfile, zipfile
from pathlib import Path
from io import BytesIO
from numbers import Number
import geopandas as gpd
from datetime import datetime as dt
from osgeo import gdal, ogr, osr
import numpy as np
from cdr import cdr_utils
from django.conf import settings
from django.forms.models import model_to_dict
from django.core.exceptions import BadRequest
from django.http import HttpResponse
from django.db import connection
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

def process_params(req,params,post=False,post_json=False):
    r = req.GET if not post else req.POST
    if post_json:
        body = req.body.decode('utf-8')#.replace("'",'"')
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
    simplify = 0.002 if t_srs == 4326 else 200
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
    prj = ds.GetProjection()
    srs = osr.SpatialReference(prj.title())
    units = srs.GetLinearUnitsName()
    #print(tif_path, units, xres)
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


def sync_cdr_prospectivity_datasources_to_datalayer(data_source_id=None):
    '''
    data_source_id: (optional) filter by data source ID if needed
    '''
    
    ### Pull layers from CDR
    cdr = cdr_utils.CDR()
    res = cdr.get_prospectivity_data_sources()

    #print(json.dumps(res[0],indent=4))
    #blerg

    for ds in res:
        if data_source_id and ds['data_source_id'] != data_source_id:
            continue
        
        if 'user_upload_example' in ds['data_source_id']:
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
            

def sync_cdr_prospectivity_outputs_to_outputlayer(
        layer_id=None,
        cma_id=None,
        sync_remote_to_local=True, # <- downloads files to local disk to speed rendering
    ):
    '''
    data_source_id: (optional) filter by data source ID if needed
    '''
    
    ### Pull layers from CDR
    cdr = cdr_utils.CDR()
    res = cdr.get_prospectivity_output_layers()

    #print(json.dumps(res[0],indent=4))
    #blerg
    dsids = []
    for i,ds in enumerate(res):
        #print('here')
        if layer_id and ds['layer_id'] != layer_id:
            continue
        
        #print('woop')
        if ds['download_url'].split('.')[-1] != 'tif':
            continue
        
        if cma_id and ds['cma_id'] != cma_id:
            continue

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
                'data_format': 'tif',
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
            
            
def getOutputLayers():
    return models.OutputLayer.objects.all().order_by('category','subcategory','name')


def sync_remote_outputs_to_local():
    dd = f'/net/vm-apps2{settings.TILESERVER_LOCAL_SYNC_FOLDER}'

    # for datalayer in dm_util.getDataLayers():
    for datalayer in getOutputLayers():
        #print(datalayer.download_url)

        ofile = os.path.join(dd,f'{datalayer.data_source_id}.tif')

        if not os.path.exists(ofile):
            print('syncing to local:',datalayer.download_url)
            bn = os.path.basename(datalayer.download_url)
            with requests.get(datalayer.download_url) as r:
                with open(ofile,'wb') as f:
                    #print(r.content)
                    f.write(r.content)

            # Compress and add overviews
            temp_tif = 'temp_compress.tif'
            cmd = f'gdal_translate -co "COMPRESS=LZW" -co "BIGTIFF=YES" {ofile} {temp_tif}'
            os.system(cmd)
            shutil.move(temp_tif, ofile)

            os.system(f'gdaladdo {ofile} 2 4 8 16')

    
def get_datalayers_for_gui(data_source_ids=[]):
    datalayers = {'User uploads':{}} # this object sorts by category/subcategory
    datalayers_lookup = {} # this object just stores a lookup by 'name'
    filters = {'disabled': False}
    if data_source_ids:
        filters['data_source_id__in'] = data_source_ids
    
    print(filters)
    for Obj in (models.DataLayer, models.OutputLayer):
        for d in Obj.objects.filter(**filters).order_by(
                'category','subcategory','name'
            ):
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
    
    cog_filename = '/home/mgbillmi/PROCESSING/cogify_test.tif'
    
    #with open(cog_filename,'wb') as f:
    #    f.write(data)
    
    #output_memfile = MemoryFile()
    output_memfile = os.path.join(
        settings.BASE_DIR,
        'cma',
        'temp',
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

    return output_memfile#open(output_memfile,'rb')#.read()

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
    print('bounds',bounds)
    print('pixel size',pixel_size)

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
            'output_temporal_aggregations',
            'nawfd_stochastic_use_cached',
            'output_format',
            'format_for_calculator',
            'ignore_limit',
            ):
            #v = params[p] if params[p] else '|'
            v = str(params[p]).replace(' ','') if params[p] not in (None,'None') else ''
            if p in ('bbox_polygon',):
                v = v.replace('"type":"Polygon","coordinates":','').replace('{','').replace('}','').replace('[','').replace(']','')[:150]
            k.append(v)
    
    return '|'.join(k)


def downloadShapefile(FeatureCollection, shp_name='test5'):
    '''
    Data is a list of GeoJSON features; a dict w/ 'features'
    '''
    
    # map of fields to be truncated b/c the way shapefile does this
    # automatically kind of sucks
    trunc_fields = {
        'burnedarea_id': 'id',
        'consumption_mg': 'cons_mg',
        'fuel_available_total_mg': 'fuel_mg',
        'heat_release_smoldering_kbtu': 'hr_s_kbtu',
        'heat_release_residual_kbtu': 'hr_r_kbtu',
        'heat_release_flaming_kbtu': 'hr_f_kbtu',
        'heat_release_total_kbtu': 'hr_t_kbtu',
        'fuel_moisture_1000hr_pct': 'fm_1khr_pc',
        'fuel_moisture_litter_pct': 'fm_litt_pc',
        'fuel_moisture_duff_pct': 'fm_duff_pc',
    }

    shp_tempfile = os.path.join('/tmp', '{}.shp'.format(shp_name))

    # "4" = ESRI Shapefil
    #driver = ogr.GetDriver(6)
    driver = ogr.GetDriverByName('ESRI Shapefile')

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
            fn = field if field not in trunc_fields else trunc_fields[field]
                
            v = data[0]['properties'][field]
            dtype = ogr.OFTString  # assume string by default
            if v:
                dtype = type_dict[type(v)]
            if not dtype:
                continue
            
            layer.CreateField(ogr.FieldDefn(str(fn), dtype))


        # Now add data
        for row in data:
            feature = ogr.Feature(layer.GetLayerDefn())
            for p, v in row['properties'].items():
                p2 = p if p not in trunc_fields else trunc_fields[p]
                u = v
                if v:
                    dtype = type_dict[type(v)]
                if not dtype:
                    continue
                #if type(v) == unicode:
                    #u = str(v)
    
                feature.SetField(str(p2), u)
                #if 'fuel_moisture' in p:
                    #tmp1 = p2
                    #tmp2 = str(p2)
                    #tmp3 = [feature.GetField(x) for x in range(len(fields))]
                    #blerg

            poly = ogr.CreateGeometryFromJson(json.dumps(row['geometry']))
            feature.SetGeometry(poly)
            layer.CreateFeature(feature)

            feature = None
            poly = None

        ds = None
        
    # Now write the files to zip
    bytes_io = BytesIO()
    with zipfile.ZipFile(bytes_io, 'w', zipfile.ZIP_DEFLATED) as archive:
        for ext in ('.shp','.dbf','.shx','.prj'):
            f = shp_tempfile.replace('.shp',ext)
            archive.write(f,os.path.basename(f))

    bytes_io.seek(0) # Go to the first byte
    response = HttpResponse(bytes_io.read(), content_type='application/zip')
    bytes_io.close() # Dispose of the in-memory file

    response['Content-Disposition'] = 'attachment; filename="{}.zip"'.format(shp_name)
    
    return response
