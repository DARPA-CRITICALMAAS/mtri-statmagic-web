"""
URL configuration for statmagic project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from cma import views as cma_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('home', cma_views.home),
    path('get_mineral_sites', cma_views.get_mineral_sites),
    path('get_metadata', cma_views.get_metadata),
    #path('create_datacube', cma_views.create_datacube),
    path('initiate_cma', cma_views.initiate_cma),
    path('submit_model_run', cma_views.submit_model_run),
    path('get_vectorfile_as_geojson', cma_views.get_vectorfile_as_geojson),
    path('get_geojson_from_file', cma_views.get_geojson_from_file),
    path('get_fishnet', cma_views.get_fishnet),
    path('upload_datalayer', cma_views.upload_datalayer),
    path('get_model_outputs', cma_views.get_model_outputs),
    path('get_model_run', cma_views.get_model_run),
    path('get_model_runs', cma_views.get_model_runs),
    path('recreate_mapfile', cma_views.recreate_mapfile),
    path(r'', cma_views.home),
]
