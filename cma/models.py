from django.db import models
from django.contrib.gis.db.models import MultiPolygonField, PolygonField
from django.contrib.postgres.fields import ArrayField

# Create your models here.

class DisplayLayer(models.Model):
    '''
    Abstract model for WMS (MapServer)-enabled layers
    '''
    class Meta:
        abstract = True
        
    name = models.CharField(
        max_length=200,
        #unique=True,
        help_text='Equivalent to evidence_layer_raster_prefix in CDR schema'
    )
    name_alt = models.CharField(max_length=300,help_text='Display name (prettified)',null=True,blank=True)
    description = models.CharField(max_length=2000,null=True,blank=True)
    data_source_id = models.CharField(max_length=300,unique=True)
    data_format = models.CharField(
        max_length=100,
        choices=(
            ('tif','tif',),
            ('shp','shp',)
        ),
        blank=True, null=True
    )
    
    category = models.CharField(max_length=40,null=True,blank=True)
    subcategory = models.CharField(max_length=40,null=True,blank=True)
    
    download_url = models.CharField(max_length=1000)
    stats_minimum = models.FloatField(null=True,blank=True)
    stats_maximum = models.FloatField(null=True, blank=True)
    attribute_stats = models.JSONField(null=True,blank=True,help_text='This field is for vector files; it maps the attribute table columns to min/max values to use for tile server display')
    spatial_resolution_m = models.FloatField(null=True,blank=True)
    color = models.CharField(max_length=20,null=True, blank=True)
    disabled = models.BooleanField(default=False)
    extent_geom = PolygonField(null=True, blank=True)

class OutputLayer(DisplayLayer):
    class Meta:
        db_table = 'outputlayer'
        
    system = models.CharField(max_length=30,null=True, blank=True)
    system_version = models.CharField(max_length=200,null=True, blank=True)
    model = models.CharField(max_length=200,null=True, blank=True)
    model_version = models.CharField(max_length=200,null=True, blank=True)
    output_type = models.CharField(max_length=200,null=True, blank=True)
    cma_id = models.CharField(max_length=200,null=True, blank=True)
    #title = models.CharField(max_length=20,null=True, blank=True) # <- 'title' in the CDR will be mapped to 'name'
    model_run_id = models.CharField(max_length=200,null=True, blank=True)
    

class DataLayer(DisplayLayer):
    class Meta:
        db_table = 'datalayer'
        
    publication_date = models.DateTimeField(null=True,blank=True)
    authors = ArrayField(
        models.CharField(max_length=60),
        null=True,
        blank=True
    )
    #data_source_id = models.CharField(max_length=300,unique=True)
    doi = models.CharField(max_length=200,null=True,blank=True)
    
    #source = models.CharField(max_length=400)
    #external_link = models.CharField(max_length=1000, unique=True)
    #download_url = models.CharField(max_length=1000, unique=True)
    reference_url = models.CharField(max_length=1000,null=True,blank=True)
    datatype = models.CharField(max_length=60,null=True,blank=True)
    derivative_ops = models.CharField(max_length=200,null=True,blank=True)
    #subcategory_type = models.CharField(max_length=20)
    #notes = models.CharField(max_length=200, default=True, blank=True)
    
    #stats_minimum = models.FloatField(null=True,blank=True)
    #stats_maximum = models.FloatField(null=True, blank=True)
    #spatial_resolution_m = models.FloatField(null=True,blank=True)
    #color = models.CharField(max_length=20,null=True, blank=True)
    #disabled = models.BooleanField(default=False)
    
    
class CRS(models.Model):
    class Meta:
        db_table = 'crs'
        
    name = models.CharField(max_length=200, unique=True)
    proj4text = models.CharField(max_length=2000)
    units = models.CharField(max_length=10)
    default_resolution = models.FloatField()
    srid = models.CharField(max_length=100,null=True, unique=True)
    
    
class ProcessingStep(models.Model):
    def __str__(self):
        return self.name
    class Meta:
        db_table = 'processingstep'
        
    name = models.CharField(max_length=40,unique=True)
    name_pretty = models.CharField(max_length=100,null=True)
    description = models.CharField(max_length=1000,null=True)
    
    
class ProspectivityModelType(models.Model):
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'prospectivity_model_type'
        
    name = models.CharField(max_length=100,unique=True)
    name_pretty = models.CharField(max_length=200,null=True)
    description = models.CharField(max_length=1000,null=True)
    author = models.CharField(max_length=60,null=True,blank=True)
    organization = models.CharField(max_length=60,null=True,blank=True)
    model_type = models.CharField(max_length=60,null=True,blank=True)
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
            ('range_double', 'range_double'),
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
    
    
class ProspectivityModelTypeParameter(ProcessParameter):
    def __str__(self):
        return f'{self.model}__{self.name}'
    
    class Meta:
        db_table = 'prospectivity_model_type_parameter'
        unique_together = ('model','name')
        
    model = models.ForeignKey(ProspectivityModelType,on_delete=models.CASCADE)
    
    
class ProcessingStepParameter(ProcessParameter):
    def __str__(self):
        return f'{self.processingstep}__{self.name}'
    
    class Meta:
        db_table = 'processingstep_parameter'
        unique_together = ('processingstep','name')
        
    processingstep = models.ForeignKey(ProcessingStep,on_delete=models.CASCADE)
