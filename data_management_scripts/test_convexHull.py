import json

import ogr, osr, rasterio, xarray, rioxarray, pyproj
from shapely.geometry import box
import dm_util
from osgeo import gdal, ogr
import numpy as np

dm_util.util.sync_cdr_prospectivity_datasources_to_datalayer()
blerg

tif = '/home/mgbillmi/Downloads/3ef30a39eab34cc2a305f7b6771467e6.tif'
shp = '/vsimem/test_convexhull.geojson'


tif = 'https://s3.amazonaws.com/public.cdr.land/prospectivity/inputs/b4050056d38a449fa3d940008e277145.tif'

gj = dm_util.util.get_extent_geom_of_raster(tif)
print(gj)
blerg

xds = xarray.open_dataarray(tif)
#transformer = pyproj.Transformer.from_crs(xds.rio.crs, "EPSG:4326", always_xy=True)
transform_bounds_box = box(*xds.rio.transform_bounds("EPSG:4326"))

gj = ogr.CreateGeometryFromWkt(str(transform_bounds_box)).ExportToJson()
print(gj)

#print(transform_bounds_box)
#with rasterio.open(tif) as ds:
#    print(ds.bounds)

blerg

# Open raster, pull out metadata and data
ds = gdal.Open(tif)

band1 = ds.GetRasterBand(1)
rows = ds.RasterYSize
cols = ds.RasterXSize
nodata = band1.GetNoDataValue()
srs = dm_util.util.get_tif_srs(ds)#.GetAuthorityCode(None)

#print(srs.GetAuthorityCode(None))

arr = band1.ReadAsArray(0, 0, cols, rows)

# Create in-memory version that is reclassified to binary
driver = gdal.GetDriverByName('MEM')
ds_reclass = driver.Create('', cols, rows, 1, band1.DataType)

# Set metadata on the temp file
ds_reclass.SetGeoTransform(ds.GetGeoTransform())
ds_reclass.SetProjection(ds.GetProjection())
band_reclass = ds_reclass.GetRasterBand(1)
band_reclass.SetNoDataValue(0)
outData = np.copy(arr)

# Reclassify so that everything that is not nodata = 1
outData[arr!=nodata] = 1
outData[arr==nodata] = 0

#print(outData)
#print(outData.shape)

# Write reclassed data
band_reclass.WriteArray(outData,0,0)
band_reclass.FlushCache()

del ds
del outData

# Now convert to vector
drv = ogr.GetDriverByName("Memory")
dst_ds = drv.CreateDataSource(shp)
dst_layer = dst_ds.CreateLayer(shp, srs=srs)

gdal.Polygonize(band_reclass,band_reclass, dst_layer, -1)


# Finally, simplify/transform and convert to geojson

# For these brief visualization extents, set to a pretty coarse simplification
# level: 5km
simplify_prec = 0.05 if srs.GetAuthorityCode(None) in ('4269','4326','3857') else 5000

multi = ogr.Geometry(ogr.wkbMultiPolygon)
for feature in dst_layer:
    multi.AddGeometry(feature.geometry().ForceTo2D().Simplify(simplify_prec))

t_srs = osr.SpatialReference()
t_srs.ImportFromEPSG(4326)
transform = osr.CoordinateTransformation(
    srs,
    t_srs
)
multi.Transform(transform)
gj = json.loads(multi.UnionCascaded().ExportToJson())



#with open('text_gj.geojson','w') as f:
#    f.write(json.dumps(gj))

