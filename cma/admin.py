from django.contrib import admin
from . import models

# Register your models here.
class ModelAdmin(admin.ModelAdmin):
    list_display = ('name','name_pretty','description')
    
class ModelParameterAdmin(admin.ModelAdmin):
    list_display = ('__str__','group_name','name_pretty','order')

class ProcessingStepAdmin(admin.ModelAdmin):
    list_display = ('name','name_pretty','description')
    
class CRSAdmin(admin.ModelAdmin):
    list_display = ('name','units','default_resolution')

admin.site.register(models.Model, ModelAdmin)
admin.site.register(models.ModelParameter, ModelParameterAdmin)
admin.site.register(models.ProcessingStep, ProcessingStepAdmin)
admin.site.register(models.CRS, CRSAdmin)
