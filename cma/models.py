from django.db import models
from django.contrib.postgres.fields import ArrayField

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
    
class ProcessingStep(models.Model):
    class Meta:
        db_table = 'processingstep'
        
    name = models.CharField(max_length=40,unique=True)
    name_pretty = models.CharField(max_length=100,null=True)
    description = models.CharField(max_length=1000,null=True)
    
class Model(models.Model):
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'model'

        
    name = models.CharField(max_length=100,unique=True)
    name_pretty = models.CharField(max_length=200,null=True)
    description = models.CharField(max_length=1000,null=True)
    uses_datacube = models.BooleanField(default=True)
    buttons = models.JSONField(null=True,blank=True) # <- define model run buttons
    
class ModelParameter(models.Model):
    def __str__(self):
        return f'{self.model}__{self.name}'
    
    class Meta:
        db_table = 'model_parameter'
        ordering = ['order']
        unique_together = ('model','name')
        
    model = models.ForeignKey(Model,on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    name_pretty = models.CharField(max_length=100,null=True)
    description = models.CharField(max_length=2000,null=True,blank=True)
    units =  models.CharField(max_length=20, null=True,blank=True)
    input_type = models.CharField(
        max_length=30,
        choices = (
            ('number','number'),
            ('text','text'),
            ('checkbox','checkbox'),
            ('select','select'),
        )
    )
    html_attributes = models.JSONField(null=True,blank=True,help_text="Use this field to provide optional HTML element attributes to include with the input or select elemetnt") # <- (optional) add additional HTML element attributes here
    options = ArrayField(models.CharField(max_length=20),null=True,blank=True)  # <- (optional) for 'select' input types, option values
    group_name = models.CharField(max_length=100, null=True,blank=True)
    only_show_with = models.ForeignKey('self',on_delete=models.CASCADE,null=True,blank=True)
    order = models.IntegerField()
