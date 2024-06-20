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
    path('create_datacube', cma_views.create_datacube),
    path('run_cma_model', cma_views.run_cma_model),
    path('get_shp_as_geojson', cma_views.get_shp_as_geojson),
    path('get_geojson_from_file', cma_views.get_geojson_from_file),
    path(r'', cma_views.home),
]
