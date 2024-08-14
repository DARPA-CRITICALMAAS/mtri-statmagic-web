import atexit, json, os, math, pg, re, sys
from osgeo import ogr
currpath = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(currpath))
os.environ["DJANGO_SETTINGS_MODULE"] = "statmagic.settings"
import django
django.setup()
from django.conf import settings
#from cma import models
from cma.models import DataLayer
import cma.models as models
import cma.util as util

DB = settings.DATABASES['default']

# PostgreSQL connection params
def getcon(host=DB['HOST']):
    return pg.connect(DB['NAME'],host,int(DB['PORT']), None, DB['USER'],DB['PASSWORD'])

con1 = getcon()

@atexit.register
def exit():
    if con1:
        con1.close()


def getDataLayers():
    return DataLayer.objects.all().order_by('category','subcategory','name')


def create_fishnet(
        output_file,
        xmin, xmax, ymin, ymax,
        resolution,
    ):

    # get rows
    rows = math.ceil((ymax - ymin) / resolution)

    # get columns
    cols = math.ceil((xmax - xmin) / resolution)

    # create output file
    outDriver = ogr.GetDriverByName('ESRI Shapefile')
    if os.path.exists(output_file):
        os.remove(output_file)
    outDataSource = outDriver.CreateDataSource(output_file)
    outLayer = outDataSource.CreateLayer(
        output_file,
        geom_type=ogr.wkbLineString
    )
    featureDefn = outLayer.GetLayerDefn()

    # create grid cells
    for i in range(cols+1):
        line = ogr.Geometry(ogr.wkbLineString)
        px = xmin + (i * resolution)
        line.AddPoint(px, ymin)
        line.AddPoint(px, ymax)

        outFeature = ogr.Feature(featureDefn)
        outFeature.SetGeometry(line)
        outLayer.CreateFeature(outFeature)
        outFeature = None

    for j in range(rows+1):
        line = ogr.Geometry(ogr.wkbLineString)
        py = ymin + (j * resolution)
        line.AddPoint(xmin, py)
        line.AddPoint(xmax, py)

        outFeature = ogr.Feature(featureDefn)
        outFeature.SetGeometry(line)
        outLayer.CreateFeature(outFeature)
        outFeature = None

    # Save and close DataSources
    outDataSource = None

    # Now clip
    outDataSource = outDriver.CreateDataSource('test_fishnet_clipped.shp')
    outLayerClip = outDataSource.CreateLayer('test_fishnet_clipped.shp', geom_type=ogr.wkbLineString)

    clip_polygon = ogr.CreateGeometryFromWkt(extent_wkt)
    ogr.Layer.Clip(outLayer,clip_polygon,outLayerClip)