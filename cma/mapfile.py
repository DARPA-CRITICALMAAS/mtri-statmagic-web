import codecs, copy, os, sys, tempfile
import json
from itertools import chain
from django.conf import settings
from django.forms.models import model_to_dict
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from osgeo import gdal, osr
from . import util
import numpy as np

# From: https://colorbrewer2.org/#type=diverging&scheme=RdYlBu&n=11
COLORS_DIVERGING = [
    [165,0,38],
    [215,48,39],
    [244,109,67],
    [253,174,97],
    [254,224,144],
    [255,255,191],
    [224,243,248],
    [171,217,233],
    [116,173,209],
    [69,117,180],
    [49,54,149],
]
COLORS_DIVERGING.reverse()

# From: https://colorbrewer2.org/#type=qualitative&scheme=Paired&n=10
COLORS_QUALITATIVE = [
    [166,206,227],
    [31,120,180],
    [178,223,138],
    [51,160,44],
    [251,154,153],
    [227,26,28],
    [253,191,111],
    [255,127,0],
    [202,178,214],
    [106,61,154],
]


def get_mapfile_path():
    mfmod = '' if settings.MAPSERVER_SERVER == 'vm-apps2' else '2'
    mapfile_production_dir = f'/net/{settings.MAPSERVER_SERVER}/var/www/mapfiles{mfmod}'
    
    return os.path.join(mapfile_production_dir, settings.MAPFILE_FILENAME)
  

def scrub_wms_layername(name):
    return name.replace('.','')


def getCLASS(cmap,attribute='pixel'):
    c = 'COLOR'
    w = ''
    if attribute != 'pixel':
        c = 'OUTLINECOLOR'
        w = 'WIDTH 2.0'

    return '\n'.join([
        f'''
        CLASS
            EXPRESSION ([{attribute}] = {k})
            STYLE
                {c} {cmap[k]}
                {w}
            END
        END
        '''
        for k in sorted(cmap)
    ])


def openRaster(ds_path):
    td = None
    ds_path2 = ds_path
    if settings.TILESERVER_LOCAL_SYNC_FOLDER in ds_path:
        ds_path2 = f'/net/{util.settings.MAPSERVER_SERVER}/{ds_path}'
        
    if ' ' in ds_path:
        td = tempfile.TemporaryDirectory()
        url = r['download_url'].replace('/vsicurl_streaming/','')
        os.system(f'wget -P {td.name} "{url}"')
        tp = os.path.join(td.name,os.path.basename(ds_path))
        ds = gdal.Open(tp)
    else:
        ds = gdal.Open(ds_path2)
        
    return ds


def getClassesForQualitative(data_rng):
    '''
    Returns mapfile CLASS specifications for a given data range for
    qualitative data.  Assumes classes are represented as successive integers
    in the provided data range.

        data_rng: [min data, max data]
    '''

    cls = ''
    for i,pval in enumerate(range(int(data_rng[0]),int(data_rng[1])+1,1)):
        color_index = i % len(COLORS_QUALITATIVE)
        color = ' '.join([str(c) for c in COLORS_QUALITATIVE[color_index]])
        cls += f'''
           CLASS
               NAME "{pval}" 
               EXPRESSION ([pixel] > {pval-1} AND [pixel] < {pval+1})
               STYLE
                   COLOR {color}
               END
           END
       '''

    return cls
    
    
    

def getClassesForRange(
        data_rng,
        break_colors,
    ):
    '''
        data_rng: [min data, max data]
    '''
    numClasses = len(break_colors)#10

    breaks = list(reversed([break_colors[int(i*len(break_colors)/numClasses)] 
                for i in range(numClasses)
            ] + [break_colors[-1]]))

    # build default rainbow stretch from the provided data range
    raster_class = ''
    
    # Tack on the first class         
    # name, expression for last value
    upper = data_rng[1]
    color = ' '.join([str(x) for x in break_colors[-1]])
    name = f'{upper}+'
    expression = f'[pixel] > {upper}'
    raster_class += f'''
        CLASS 
            NAME "{name}"
            EXPRESSION ({expression})
            STYLE
                COLOR {color}
            END 
        END
    '''
    
    rng = data_rng[1] - data_rng[0]
    for i in range(len(breaks)-1):
        b = breaks[i]
    
        high_color = ' '.join([str(x) for x in b])
        low_color = break_colors[-1]
        
        upper = data_rng[1] - rng*(i/float(numClasses))
        lower = data_rng[1] - rng*((i+1)/float(numClasses))
        
        if i < len(breaks)-1:
            low_color = ' '.join([str(x) for x in breaks[i+1]])
        
        # default name, expression
        name = f'{lower} - {upper}'
        expression = f'[pixel] >= {lower} AND [pixel] < {upper}'
        raster_class += f'''
            CLASS 
                NAME "{name}"
                EXPRESSION ({expression})
                STYLE
                    COLORRANGE {low_color} {high_color}
                    DATARANGE {lower} {upper}
                    RANGEITEM "pixel"
                    COLOR {low_color}
                END 
            END
        '''
        
    return raster_class


def write_mapfile(
        mapfile_title = 'StatMAGIC data layers',
        processing_scale_buckets = 101,
    ):
    from .models import DataLayer, OutputLayer, ProcessedLayer
    '''
    processing_scale_buckets:   Parameter used to specify number of buckets to
                                divide data into for classification; MASSIVELY 
                                improves performance (lower = faster)
    
    '''
    
    projection = 'AUTO'
    
    mapfile_name = get_mapfile_path()
    mapfile_path = mapfile_name.replace(
        '/net/{}'.format(settings.MAPSERVER_SERVER),
        ''
    )

    # Colors retrieved from here:
    # https://colorbrewer2.org/#type=qualitative&scheme=Paired&n=12
    #
    # (skipping the paler colors b/c they don't show enough contrast)
    colors = [
        #[166, 206, 227],
        [31, 120, 180],
        #[178, 223, 138],
        [51, 160, 44],
    # [251, 154, 153],
        [227, 26, 28],
        #[253, 191, 111],
        [255, 127, 0],
    # [202, 178, 214],
        [106, 61, 154],
    # [255, 255, 153],
        [177, 89, 40],
    ]

    #########
    # Build rasters dict from database

    datalayers = DataLayer.objects.filter(disabled=False).order_by('category','subcategory','name')
    outputlayers = OutputLayer.objects.filter().order_by('category','subcategory','name')
    processedlayers = ProcessedLayer.objects.filter().order_by('category','subcategory','name')
    datasets = list(chain(datalayers, outputlayers, processedlayers))
    #.values(
        #'name',
        #'download_url',
        #'stats_minimum',
        #'stats_maximum',
    #)

    rasters = {}
    for i,dataset in enumerate(datasets):
        r = model_to_dict(dataset)
        is_likelihood_layer = 'ikelihood' in r['description']
        is_qualitative_layer = 'est Matching Units' in r['description']
        
        # Ignore any non-rasters for now
        if not r['download_url']:# or r['data_format'] != 'tif':
            continue

        # Processing path to raster
        #   (replace spaces with '+' or URLs won't work)
        ds_path = r['download_url'].replace(' ','+')
        ext = ds_path.split('.')[-1]
        #print(ext)
        if 'http' in ds_path:
            # WARNING: temporarily, model outputs are sync'd locally
            if '.cdr.' in ds_path and 'model' not in r and ext not in ('zip',): 
                ds_path = f'/vsicurl_streaming/{ds_path}'
            else:
               
                if ext == 'zip' and 'plots' not in r['download_url'] and 'additional' not in r['download_url'] : # assume .zip data sources are shapefiles
                    ext = 'shp'
                
                # NOTE: for now sync'ing these locally '
                ds_path = os.path.join(
                    settings.TILESERVER_LOCAL_SYNC_FOLDER,
                    f'{r["data_source_id"]}.{ext}'#os.path.basename(ds_path)
                )

        # Load required params
        rkey = r['data_source_id']
        bn = os.path.basename(ds_path)
        ext = bn.split('.')[-1]
        
        rasters[rkey] = r
        rasters[rkey]['download_url'] = ds_path
        rasters[rkey]['wms_layername'] = r['data_source_id']
        rasters[rkey]['layer_type'] = dataset.vector_format if ext in ('shp','SHP','js') else 'RASTER'
        rasters[rkey]['wms_title'] = rkey
        
         # Add color is not already set 
        if not dataset.color:
            color = colors[i % len(colors)]
            dataset.color = ','.join([str(c) for c in color])
            if is_likelihood_layer:
                dataset.color = 'diverging'
            dataset.save()
            
        if is_likelihood_layer:
            dataset.color = 'diverging'
            dataset.save()
            
        color = dataset.color.replace(',',' ') 

        
        # Assume all LOS rasters are scaled 0-1
        dr = None
        proc = ''
        classification = ''
        connection_type = ''
        connection = ''
        layer_type = 'RASTER'
    
        ds_path2 = ds_path
        if 'cdr' not in ds_path and util.settings.MAPSERVER_SERVER not in ds_path:
            ds_path2 = f'/net/{util.settings.MAPSERVER_SERVER}/{ds_path}'
            
        # Run sync script if one of the outputlayers has not been locally
        # downloaded
        if '/net/' in ds_path2 and not os.path.exists(ds_path2):
            util.sync_cdr_prospectivity_outputs_to_outputlayer(rkey)
            util.sync_remote_outputs_to_local(rkey)
    
        if ext in ('js','json','geojson'):
            connection_type = 'CONNECTIONTYPE OGR'
            connection = f'CONNECTION "{r["path"]}"'

        if ext == 'shp':
            util.process_vector_for_mapfile(dataset)
            dr = [r['stats_minimum'], r['stats_maximum']]
            
            if dataset.vector_format == 'POINT':
                classification = f'''
                    CLASS
                        STYLE
                            OUTLINECOLOR {color} 
                            SIZE 1
                            SYMBOL "circle"
                            WIDTH 1.0
                        END
                    END
                '''
            if dataset.vector_format == 'LINE':
                classification = f'''
                    CLASS
                        STYLE
                            OUTLINECOLOR {color} 
                            COLOR {color}
                            WIDTH 5.0
                        END
                    END
                '''
            if dataset.vector_format == 'POLYGON':
                classification = f'''
                    CLASS
                        STYLE
                            OUTLINECOLOR {color}
                            COLOR {color}
                            OPACITY 30
                            WIDTH 3.0
                        END
                    END
                '''
            
        elif ext in ('tif','upload'):

            # Retrieve extent_geom if not already loaded
            if r['extent_geom'] is None:
                print('getting extent_geom for:',ds_path)
                
                #ds = openRaster(ds_path)
                gj = util.get_extent_geom_of_raster(ds_path2)

                if gj:
                    gj = json.dumps(gj)
                    geom = GEOSGeometry(gj)

                dataset.extent_geom = geom#GEOSGeometry(gj)
                dataset.save()

            # Retrieve data range if not already loaded
            if r['stats_minimum'] is None and r['stats_maximum'] is None:
                print('extracting stats for:',ds_path)
                ds = openRaster(ds_path)
                    
                stats = ds.GetRasterBand(1).GetStatistics(0,1) # min,max,mean,std
                del ds
                #if td:
                    #td.cleanup()
                dr = [stats[0],stats[1]+(stats[1]*0.0000001)]
                dataset.stats_minimum = stats[0]
                dataset.stats_maximum = stats[1]
                dataset.save()
                            
            else:
                dr = [r['stats_minimum'], r['stats_maximum']+(r['stats_maximum']*0.0000001)]
                
            # Retrieve spatial resolution if not already loaded
            # This just needs to be an approximation for setting templates
            if r['spatial_resolution_m'] is None:
                xres = util.get_tif_resolution(ds_path2)
                dataset.spatial_resolution_m = int(xres)
                dataset.save()
    
       
            # For rasters, color scale is the assigned color stretched b/t
            # the min/max pixel values.

            classification = f'''
                CLASS
                    NAME "Color"
                    EXPRESSION ([pixel] >= {dr[0]} AND [pixel] <= {dr[1]})
                    STYLE
                            COLORRANGE 256 256 256 {color}
                            DATARANGE {dr[0]} {dr[1]}
                            RANGEITEM "pixel"
                            COLOR 256 256 256
                    END
                END
            '''
            
            # For likelihood rasters, use diverging color scale
            if is_likelihood_layer:
                classification = getClassesForRange(dr, COLORS_DIVERGING)
        
            if is_qualitative_layer:
                classification = getClassesForQualitative(dr)
        
        else:
            del rasters[rkey]
            continue
            
        rasters[rkey]['data_range'] = dr
        rasters[rkey]['processing'] = proc
        rasters[rkey]['connection'] = connection
        rasters[rkey]['connection_type'] = connection_type
        rasters[rkey]['extent'] = [-180,0,180,90]
        rasters[rkey][layer_type] = layer_type
        
        if classification:
            rasters[rkey]['classification'] = classification
        #if r['wms_group']:
            #rasters[rkey]['group'] = r['wms_group']
        #print(bn,proc)
        
    ######################
    # Now process into MapServer mapfile LAYER entries
    
    layer_text = ''
    agg_extent = []
    getmaps = []
    for raster in sorted(rasters, reverse=True):
        #print(raster)

        robj = rasters[raster]
        raster_path = robj['download_url']

        projection = '"init=epsg:4326"' if 'Geophysics_LAB_HGM_USCanada_cog.tif' in raster_path else 'AUTO'

        layer_type = 'RASTER'
        if robj['layer_type']:
            layer_type = robj['layer_type']

        # Get extent and process aggregate extent
        #print(robj)
        te = robj['extent']
        te_str = ' '.join([str(q) for q in te])
        te_str_abbrev = ','.join(['{:.4f}'.format(x) for x in te])
        if len(agg_extent) == 0:
            agg_extent = te
        else:
            agg_extent[0] = min(te[0], agg_extent[0])
            agg_extent[1] = min(te[1], agg_extent[1])
            agg_extent[2] = max(te[2], agg_extent[2])
            agg_extent[3] = max(te[3], agg_extent[3])

        wms_layername = scrub_wms_layername(robj['wms_layername'])
        wms_title = robj['wms_title']

        #proc = robj['wmslayerprocessing__processing']
        proc = robj['processing']
        processing = 'PROCESSING "BANDS=1"' if (not proc and layer_type == 'RASTER') else proc

        processing_scale = ''
        processing_range = '0,100'
        if robj['data_range']:
            dr_list = robj['data_range']
            if type(dr_list[0]) == list:
                processing_scale = ""
                for i,dr in enumerate(dr_list):
                    processing_range = ','.join([str(x) for x in dr])
                    processing_scale += '\nPROCESSING "SCALE_{}={}\nPROCESSING "NODATA=3"\n"'.format(i+1,processing_range)
                processing_scale += '\nPROCESSING "SCALE_BUCKETS={}"\n'.format(processing_scale_buckets)
            else:
                processing_range = ','.join([str(x) for x in robj['data_range']])
                processing_scale = f'''
                    PROCESSING "SCALE={processing_range}"
                    PROCESSING "SCALE_BUCKETS={processing_scale_buckets}"
                '''

        classification = ''
        if 'classification' in robj:
            classification = robj['classification']
            

        connection = robj['connection']
        connection_type = robj['connection_type']
        #if 'is_LOS' in robj:
            #classification = '''
                #CLASS 
                    #EXPRESSION ([pixel] = 0)
                    #STYLE
                        #COLOR 255 102 102
                    #END
                #END
                #CLASS 
                    #EXPRESSION ([pixel] = 1)
                    #STYLE
                        #COLOR 153 255 153
                    #END
                #END
  
            #'''
        #if 'is_hangup' in robj:
            #classification = '''
                #CLASS 
                    #EXPRESSION ([pixel] = 1)
                    #STYLE
                        #COLOR 255 102 102
                    #END
                #END
  
            #'''
        
        #cls = robj['wmslayerclassification__class_map']
        PROJ = '''
            PROJECTION
                {projection}
            END  
        '''.format(**locals())
        #if robj['layer_type'] == 'POLYGON':
            ##PROJ = ''
            #classification = '''
                #CLASS  
                    #STYLE
                        #OUTLINECOLOR 50 50 255 
                        #COLOR 0 0 150
                    #END
                #END
            #'''

        group = ''
        if 'group' in robj and robj['group']:
            group = 'GROUP "{}"'.format(robj['group'])
        layer = '''
            LAYER
                NAME "{wms_layername}"
                {connection_type}
                {connection}
                DATA "{raster_path}"
                {group}
                TYPE {layer_type}
                STATUS ON
                DEBUG 5
                {processing}
                {processing_scale}
                {classification}
                {PROJ}
                METADATA
                    "wms_title" "{wms_title}"
                    "wms_srs"   "EPSG:4326 EPSG:3857"
                    "wms_extent" "{te_str}"
                    "wms_enable_request" "*"
                END
                
            END
        '''.format(**locals())

        # OFFSITE 0 0 0 <- makes 0 pixel values transparent

        layer_text += layer

        # Provide example GetMap request for the layer
        getmaps.append((
            f'http://{settings.MAPSERVER_SERVER}.mtri.org/cgi-bin/mapserv.fcgi?'
            'SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap'
            '&map={mapfile_path}'
            '&LAYERS={wms_layername}'
            '&height=512&width=512'
            '&format=image/png'
            '&srs=EPSG:4326'
            '&bbox={te_str_abbrev}'
            '&opacity=1').format(**locals())
        )


    #########################################
    # Now mush it all together
    aggregate_extent = ' '.join(str(x) for x in agg_extent)
    aggregate_extent = '-80.0 43.0  -76.0 45.0'

    mapfile_text = '''
    MAP
        NAME "{mapfile_title}"
        STATUS ON
        EXTENT {aggregate_extent}
        SHAPEPATH ""
        PROJECTION
            "init=epsg:4326"
        END
        SYMBOLSET "symbols.sym"
        UNITS METERS
        IMAGECOLOR 0 0 0
        TRANSPARENT ON
        IMAGETYPE jpeg
        CONFIG "CPL_DEBUG" "ON"
        CONFIG "PROJ_DEBUG" "ON"
        DEBUG 5
        CONFIG "MS_ERRORFILE" "/var/log/mapserver/error.log"
        # Start of web interface definition (including WMS enabling metadata)
        WEB
            MINSCALE 1000
            MAXSCALE 1550000

            IMAGEPATH "/var/www/docs_maps/tmp/"
            IMAGEURL "/docs_maps/tmp/"

            METADATA
                WMS_TITLE "{mapfile_title}"
                WMS_ABSTRACT "{mapfile_title}"
                WMS_CONTACTINFORMATION "mgbillmi@mtu.edu"
                WMS_ACCESSCONSTRAINTS "none"

                # change this value to match your setup
                WMS_ONLINERESOURCE "http://spatial.mtri.org/cgi-bin/mapserv"
                WMS_ENABLE_REQUEST "*"
                WMS_SRS "epsg:4326 epsg:3857"
                "wms_feature_info_mime_type" "text/html"
            END
        END
    {layer_text}
    END
    '''.format(**locals())


    # Write outputs
    with open(mapfile_name, 'w') as m:
        m.write(mapfile_text)

    #blerg
    #print(mapfile_text)

    # Tell user how to access things for testing
    #print('\n\nGetMap examples:\n')
    #for getmap in getmaps:
    #    print('\n{}'.format(getmap))


    print(('\n\nGetCapabilities for your mapfile:\n\n'
        f'http://{settings.MAPSERVER_SERVER}.mtri.org/cgi-bin/mapserv.fcgi?'
        'REQUEST=GetCapabilities&'
        'SERVICE=WMS&'
        'map={}'
    ).format(mapfile_path),file=sys.stderr)
