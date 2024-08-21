import json
import dm_util
from cdr import cdr_utils

dm_util.util.sync_cdr_prospectivity_datasources_to_datalayer(
    #data_source_id='12mhack_upload_h_res0_4891_res1_4891_cat_LayerCategoryGEOPHYSICS'
)

# ### Pull layers from CDR
# cdr = cdr_utils.CDR()
# res = cdr.get_prospectivity_data_sources()
#
# #print(json.dumps(res[0],indent=4))
# #blerg
#
#
# for ds in res:
#     if ds['format'] == 'tif':
#         #ds = r#['data_source']
#
#         #print(r)
#         #blerg
#
#         #name = ds['description'].replace(' ','_').replace('-','_').replace('(','').replace(')','')
#         name = ds['data_source_id']
#
#         dl, created = dm_util.models.DataLayer.objects.get_or_create(
#             data_source_id = ds['data_source_id'],
#             defaults = {
#                 'name' : ds['evidence_layer_raster_prefix'],
#                 'name_alt': ds['description'],
#                 'description': ds['description'],
#                 'authors': ds['authors'],
#                 'publication_date': ds['publication_date'],
#                 'doi': ds['DOI'],
#                 'datatype': ds['type'],
#                 'category': ds['category'].capitalize(),
#                 'subcategory': ds['subcategory'].capitalize().rstrip('s'),
#                 'spatial_resolution_m': ds['resolution'][0],
#                 'download_url': ds['download_url'],
#                 'reference_url': ds['reference_url'],
#                 'derivative_ops': ds['derivative_ops']
#             },
#         )
#     else:
#         print('NONTIF:',ds)
#         #dl.save()


