from django.contrib import admin
from . import models

# Register your models here.
class ProcessingStepAdmin(admin.ModelAdmin):
    list_display = ('name','name_pretty','description')
    
class CRSAdmin(admin.ModelAdmin):
    list_display = ('name','units','default_resolution')

admin.site.register(models.ProcessingStep, ProcessingStepAdmin)
admin.site.register(models.CRS, CRSAdmin)
