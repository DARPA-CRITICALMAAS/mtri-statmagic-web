'''
Backend utility code.
'''

import json, math, os, pg, random, re, requests, string
from datetime import datetime as dt
from osgeo import ogr, osr
import numpy as np
from django.conf import settings
from django.core.exceptions import BadRequest
from django.db import connection



def process_params(req,params,post=False):
    r = req.GET if not post else req.POST
    for param in params:
        if param in r:#.has_key(param):
            params[param] = r[param]
            
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
    
    if re.compile(r'^POLYGON\(([\-\.\d\(\) \+,]*)\)$').match(wkt) == None:
        raise BadRequest('WKT Polygon format is invalid: {0}'.format(wkt))
    
    #wkt_string = fix_wkt_coords(wkt_string)

    return wkt_string


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
        
    
    
