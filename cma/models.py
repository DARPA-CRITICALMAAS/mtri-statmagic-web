from django.db import models

# Create your models here.

class DataLayer(models.Model):
    class Meta:
        db_table = 'datalayer'
        
    name = models.CharField(max_length=200, unique=True)
    name_alt = models.CharField(max_length=300)
    description = models.CharField(max_length=2000, )
    source = models.CharField(max_length=400)
    #external_link = models.CharField(max_length=1000, unique=True)
    path = models.CharField(max_length=1000, unique=True)
    category = models.CharField(
        max_length=20,
        #choices = (
            #('geophysics','Geophysics'),
            #('geology', 'Geology'),
            #('geochemistry','Geochemistry'),
        #)
    )
    subcategory = models.CharField(
        max_length=20,
        #choices = (
            #('seismic','Sei'),
            #('geology', 'Geology'),
            #('geochemistry','Geochemistry'),
        #)
    )
    #subcategory_type = models.CharField(max_length=20)
    #notes = models.CharField(max_length=200, default=True, blank=True)
    data_format = models.CharField(
        max_length=100,
        choices=(
            ('tif','tif',),
            ('shp','shp',)
        )
    )
    stats_minimum = models.FloatField(null=True)
    stats_maximum = models.FloatField(null=True)
    color = models.CharField(max_length=20,null=True)
    
    
class CRS(models.Model):
    class Meta:
        db_table = 'crs'
        
    name = models.CharField(max_length=200, unique=True)
    proj4text = models.CharField(max_length=2000)
    units = models.CharField(max_length=10)
    default_resolution = models.FloatField()
    
