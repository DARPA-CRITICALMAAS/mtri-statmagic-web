from django.contrib import admin
from . import models

# Register your models here.
class ProspectivityModelTypeAdmin(admin.ModelAdmin):
    list_display = ('name','name_pretty','description')
    
class ProspectivityModelTypeParameterAdmin(admin.ModelAdmin):
    list_display = ('__str__','group_name','name_pretty','order','optional')

class ProcessingStepAdmin(admin.ModelAdmin):
    list_display = ('name','name_pretty','description')

class ProcessingStepParameterAdmin(admin.ModelAdmin):
    list_display = ('__str__','group_name','name_pretty','order')
    
class CRSAdmin(admin.ModelAdmin):
    list_display = ('name','units','default_resolution')

class DataLayerAdmin(admin.ModelAdmin):
    list_display = ('name','data_format','download_url','category','disabled')

class OutputLayerAdmin(admin.ModelAdmin):
    list_display = ('id','name','data_source_id','cma_id','model','data_format','download_url','category','disabled')


admin.site.register(models.ProspectivityModelType, ProspectivityModelTypeAdmin)
admin.site.register(models.ProspectivityModelTypeParameter, ProspectivityModelTypeParameterAdmin)
admin.site.register(models.ProcessingStep, ProcessingStepAdmin)
admin.site.register(models.ProcessingStepParameter, ProcessingStepParameterAdmin)
admin.site.register(models.CRS, CRSAdmin)
admin.site.register(models.DataLayer, DataLayerAdmin)
admin.site.register(models.OutputLayer, OutputLayerAdmin)
