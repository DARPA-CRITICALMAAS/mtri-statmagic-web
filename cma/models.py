from django.db import models
from django.contrib.postgres.fields import ArrayField

# Create your models here.

class DataLayer(models.Model):
    class Meta:
        db_table = 'datalayer'
        
    name = models.CharField(max_length=200, unique=True)
    name_alt = models.CharField(max_length=300)
    description = models.CharField(max_length=2000)
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
        max_length=30,
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
    stats_minimum = models.FloatField(null=True,blank=True)
    stats_maximum = models.FloatField(null=True, blank=True)
    color = models.CharField(max_length=20,null=True, blank=True)
    disabled = models.BooleanField(default=False)
    
    
class CRS(models.Model):
    class Meta:
        db_table = 'crs'
        
    name = models.CharField(max_length=200, unique=True)
    proj4text = models.CharField(max_length=2000)
    units = models.CharField(max_length=10)
    default_resolution = models.FloatField()
    srid = models.IntegerField(null=True, unique=True)
    
class ProcessingStep(models.Model):
    def __str__(self):
        return self.name
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
    uses_training = models.BooleanField(default=False)
    buttons = models.JSONField(null=True,blank=True) # <- define model run buttons


class ProcessParameter(models.Model):
    class Meta:
        abstract = True
        ordering = ['order']
        
    name = models.CharField(max_length=100)
    name_pretty = models.CharField(max_length=100,null=True)
    description = models.CharField(max_length=2000,null=True,blank=True)
    units =  models.CharField(max_length=20, null=True,blank=True)
    input_type = models.CharField(
        max_length=30,
        choices = (
            ('number','number'),
            ('text','text'),
            ('range','range'),
            ('checkbox','checkbox'),
            ('select','select'),
        ),
    )
    html_attributes = models.JSONField(# <- (optional) add additional HTML element attributes here
        null=True,
        blank=True,
        help_text="Use this field to provide optional HTML element attributes to include with the input or select elemetnt"
    ) 
    options = ArrayField(models.CharField(max_length=20),null=True,blank=True)  # <- (optional) for 'select' input types, option values
    group_name = models.CharField(max_length=100, null=True,blank=True)
    only_show_with = models.ForeignKey('self',on_delete=models.CASCADE,null=True,blank=True)
    order = models.IntegerField()
    optional = models.BooleanField(default=False)
    
    
class ModelParameter(ProcessParameter):
    def __str__(self):
        return f'{self.model}__{self.name}'
    
    class Meta:
        db_table = 'model_parameter'
        unique_together = ('model','name')
        
    model = models.ForeignKey(Model,on_delete=models.CASCADE)
    
    
class ProcessingStepParameter(ProcessParameter):
    def __str__(self):
        return f'{self.processingstep}__{self.name}'
    
    class Meta:
        db_table = 'processingstep_parameter'
        unique_together = ('processingstep','name')
        
    processingstep = models.ForeignKey(ProcessingStep,on_delete=models.CASCADE)
