'''
Backend utility code.
'''

import json, math, os, random, re, requests, string, tempfile
from pathlib import Path
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
from shapely import wkt
from shapely.geometry import mapping
import rasterio as rio
from rasterio.io import MemoryFile
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

def process_params(req,params,post=False,post_json=False):
    r = req.GET if not post else req.POST
    if post_json:
        r = json.loads(req.body.decode('utf-8'))
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
    

def simplify_and_transform_geojson(geometry,s_srs):
    sql = f'''
        SELECT ST_AsGeoJSON(
            ST_Simplify(
                ST_Transform(
                    ST_SetSRID(
                        ST_GeomFromGeoJSON('{str(geometry).replace("'",'"')}'),
                        {s_srs}
                    ),
                    4326
                ),
                0.002 -- simplify to ~200m 
            )
        );
    '''
    return json.loads(reduce_geojson_precision(runSQL(sql)[0]))
    

def convert_wkt_to_geojson(wkt_string):
    shape = wkt.loads(wkt_string)
    return mapping(shape)
    
def reduce_geojson_precision(data, remove_zeroes=False):
    '''
    The gdal_polygonize process used to vectorize the rasters to geojson 
    specifies polygon coordinates to an absurd level of precision (15 decimal 
    places).
    
    This function rewrites the coordinates w/ reduced precision as an
    optimization step; it reduces file size and therefore browser load times.
    '''
    
    # 5 gives us accuracy down to ~1m
    # see: https://en.wikipedia.org/wiki/Decimal_degrees
    precision = 4
    
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
        
        if ds['format'] == 'tif':
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
            

def sync_cdr_prospectivity_outputs_to_outputlayer(layer_id=None):
    '''
    data_source_id: (optional) filter by data source ID if needed
    '''
    
    ### Pull layers from CDR
    cdr = cdr_utils.CDR()
    res = cdr.get_prospectivity_output_layers()

    #print(json.dumps(res[0],indent=4))
    #blerg

    for ds in res:
        if layer_id and ds['layer_id'] != layer_id:
            continue
        
        if ds['download_url'].split('.')[0] != 'tif':
            continue
#            ds = r#['data_source']

            #print(r)
            #blerg

        #name = ds['description'].replace(' ','_').replace('-','_').replace('(','').replace(')','')
        #name = ds['layer_id']

        dl, created = models.OutputLayer.objects.get_or_create(
            data_source_id = ds['layer_id'],
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
            },
        )
        #else:
        #    print('NONTIF:',ds)

    
def get_datalayers_for_gui(data_source_id=None):
    datalayers = {'User uploads':{}} # this object sorts by category/subcategory
    datalayers_lookup = {} # this object just stores a lookup by 'name'
    filters = {'disabled': False}
    if data_source_id:
        filters['data_source_id'] = data_source_id
        
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
    output_memfile = MemoryFile()
    with MemoryFile(data).open() as memfile:
        dst_profile = cog_profiles.get("deflate")

        # Creating destination COG
        cog_translate(
            memfile,
            output_memfile.name,
            dst_profile,
            use_cog_driver=True,
            in_memory=False,
            web_optimized=True,
            overview_resampling="cubic"
        )

    return output_memfile.read()
