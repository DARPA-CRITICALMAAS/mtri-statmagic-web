import codecs, copy, os, sys
from django.conf import settings
from django.forms.models import model_to_dict
from osgeo import gdal, osr
import numpy as np




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


def write_mapfile(
        mapfile_filename = 'statmagic.map',
        mapfile_title = 'StatMAGIC data layers',
        processing_scale_buckets = 100,
    ):
    from .models import DataLayer
    '''
    processing_scale_buckets:   Parameter used to specify number of buckets to
                                divide data into for classification; MASSIVELY 
                                improves performance (lower = faster)
    
    '''
    
    projection = 'AUTO'
    
    mapfile_production_dir = '/net/{}/var/www/mapfiles'.format(settings.MAPSERVER_SERVER)
    mapfile_name = os.path.join(mapfile_production_dir, mapfile_filename)
    mapfile_path = mapfile_name.replace(
        '/net/{}'.format(settings.MAPSERVER_SERVER),
        ''
    )

    #########
    # Build rasters dict from database

    datasets = DataLayer.objects.filter()
    #.values(
        #'name',
        #'download_url',
        #'stats_minimum',
        #'stats_maximum',
    #)

    rasters = {}
    for dataset in datasets:
        r = model_to_dict(dataset)
        
        # Ignore any non-rasters for now
        if not r['download_url'] or not '.tif' in r['download_url']:
            continue

        # Processing path to raster
        tif_path = r['download_url']
        
        if 'http' in tif_path:
            if '.cdr.' in tif_path:
                tif_path = f'/vsicurl_streaming/{tif_path}'
            else:
                # NOTE: for now sync'ing these locally '
                tif_path = os.path.join(
                    settings.TILESERVER_LOCAL_SYNC_FOLDER,
                    os.path.basename(tif_path)
                )

        # Load required params
        rkey = r['name']
        bn = os.path.basename(tif_path)
        ext = bn.split('.')[-1]
        
        rasters[rkey] = r
        rasters[rkey]['download_url'] = tif_path
        rasters[rkey]['wms_layername'] = r['data_source_id']
        rasters[rkey]['layer_type'] = 'POLYGON' if ext in ('shp','SHP','js') else 'RASTER'
        rasters[rkey]['wms_title'] = rkey
        
        # Assume all LOS rasters are scaled 0-1
        dr = None
        proc = ''
        classification = ''
        connection_type = ''
        connection = ''
    
        if ext in ('js','json','geojson'):
            connection_type = 'CONNECTIONTYPE OGR'
            connection = f'CONNECTION "{r["path"]}"'

        # Retrieve data range if not already loaded
        if r['stats_minimum'] is None and r['stats_maximum'] is None:
            print(tif_path)
            ds = gdal.Open(tif_path)
            stats = ds.GetRasterBand(1).GetStatistics(0,1) # min,max,mean,std
            del ds
            dr = [stats[0],stats[1]]
            dataset.stats_minimum = stats[0]
            dataset.stats_maximum = stats[1]
            dataset.save()
                        
        else:
            dr = [r['stats_minimum'], r['stats_maximum']]
            
        # Retrieve spatial resolution if not already loaded
        # This just needs to be an approximation for setting templates
        if r['spatial_resolution_m'] is None:
    
            

            tif_path2 = tif_path
            if 'cdr' not in tif_path and 'vm-apps2' not in tif_path:
                tif_path2 = f'/net/vm-apps2/{tif_path}'
            ds = gdal.Open(tif_path2)
            _, xres, _, _, _, yres  = ds.GetGeoTransform()
            prj = ds.GetProjection()
            srs = osr.SpatialReference(prj.title())
            units = srs.GetLinearUnitsName()
            print(tif_path, units, xres)
            # If units are in degrees, do a rough approximation of
            # resolution in meters w/ assumption that 1 degree ~= 100km
            # Some projections appear incorrectly set too, so if resolution is
            # less than 1, we assume degrees
            if (units in ('degrees','Degrees','degree','Degree')) or xres < 1:
                xres *= 100000
            
            del ds
            dataset.spatial_resolution_m = int(xres)
            dataset.save()

        # Set custom color
        color = dataset.color.replace(',',' ') 
        classification = f'''
            CLASS
                NAME "Color"
                EXPRESSION ([pixel] >= {dr[0]} AND [pixel] < {dr[1]})
                STYLE
                        COLORRANGE 256 256 256 {color}
                        DATARANGE {dr[0]} {dr[1]}
                        RANGEITEM "pixel"
                        COLOR 256 256 256
                END
            END
        '''


        #if 'illshade' in rasters[rkey]['wms_title']:
            #group = '{}_{}_DEM_HILLSHADE'.format(r['sites__name'],r['name'])
            #dr = [0,254]
            
        #if 'lood_predict' in r['name']:
            #classification = '''
                #CLASS
                    #EXPRESSION ([pixel] > 0)
                    #STYLE
                        #COLOR 0 153 254
                    #END
                #END'''
            #dr = [0,1]
           
        #if 'oughness' in r['name']:
            #r['layer_type'] = 'LINE'
            #width = 6.0
            
            #classification = f'''
                #CLASS
                    #EXPRESSION ([rr] = 1)
                    #STYLE
                        #COLOR 69 117 180
                        #WIDTH {width}
                    #END
                #END
                #CLASS
                    #EXPRESSION ([rr] = 2)
                    #STYLE
                        #COLOR 255 255 191
                        #WIDTH {width}
                    #END
                #END
                #CLASS
                    #EXPRESSION ([rr] = 3)
                    #STYLE
                        #COLOR 215 48 39
                        #WIDTH {width}
                    #END
                #END
            #'''
    
      

            
        rasters[rkey]['data_range'] = dr
        rasters[rkey]['processing'] = proc
        rasters[rkey]['connection'] = connection
        rasters[rkey]['connection_type'] = connection_type
        rasters[rkey]['extent'] = [-180,0,180,90]
        
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
        print(raster)

        robj = rasters[raster]
        raster_path = robj['download_url']

        projection = '"init=epsg:4326"' if 'Geophysics_LAB_HGM_USCanada_cog.tif' in raster_path else 'AUTO'

        layer_type = 'RASTER'
        if robj['layer_type']:
            layer_type = robj['layer_type']

        # Get extent and process aggregate extent
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

        wms_layername = robj['wms_layername']
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
    print(mapfile_text)

    # Tell user how to access things for testing
    print('\n\nGetMap examples:\n')
    for getmap in getmaps:
        print('\n{}'.format(getmap))


    print(('\n\nGetCapabilities for your mapfile:\n\n'
        f'http://{settings.MAPSERVER_SERVER}.mtri.org/cgi-bin/mapserv.fcgi?'
        'REQUEST=GetCapabilities&'
        'SERVICE=WMS&'
        'map={}'
    ).format(mapfile_path),file=sys.stderr)
