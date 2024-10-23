'''
Code for testing CDR API end points (to keep cdr_utils.py clean)

'''

from cdr_utils import CDR
import json


### Testing code...
cdr = CDR()

#res = cdr.run_query('prospectivity/cmas')
#print(res)


post_data_intersect_sources = {
  "cog_ids": [],
  "feature_type": "polygon",
  "search_text": "",
  "validated": None,
  "legend_ids": [],
  "intersect_polygon": {
        "type": "Polygon",
        "coordinates": [
            [
                [-88.392,36.217],
                [-88.392,38.685],
                [-86.594,38.685],
                [-86.594,36.217],
                [-88.392,36.217]
            ]
        ]
    }
}

#res = cdr.get_cmas()
#print(res)

#res = cdr.get_model_runs('ESRI:102008_bdaf6346717f92613f3352615b6c616dab715b6c1d0674f91cf95e6a88f6a6fc__res0_500_res1_500_nickel')
# res = cdr.get_model_runs('')
#
# for r in res:
#     print(r)
# # blerg
#
# res = cdr.get_cma('ESRI:102008_dd3d7552701c9c08e8019eef6ee42db15777a33d85b44f00ab019161306f27f1__res0_10000_res1_10000_Nickel')
# print(res)
# blerg
#
# #
res = cdr.get_model_run("e77c35bdf7ae4020a9c029959b763c38")
# # print(res['event']['payload']['evidence_layers'])#.keys()))
print(res['event']['payload']['model_type'])
blerg
#
# # for p,v in res['event']['payload']['train_config'].items():
# #     print(p,v)
# # for el in res['event']['payload']['evidence_layers']:
# #     print(el['data_source']['description'],el['data_source']['format'])
# # print(len(res['event']['payload']['evidence_layers']))
# # blerg
# res = cdr.get_prospectivity_output_layers()
# for r in res:
#     print()
#     print(r)
# print(len(res))
# blerg
# #
# res = cdr.intersect_sources(json.dumps(post_data_intersect_sources))
# #res = cdr.get_cmas()
# print(res)
# print(len(res))
# print(res[0].keys())
#print(cdr.get_mineral_inventories('copper'))

# bbox_polygon_site_search = {
#     # "bbox": [
#     #     36.217,
#     #     -88.392,
#     #     38.685,
#     #     -86.594
#     # ],
#     "type": "Polygon",
#     "coordinates": [
#         [
#             [-98.392, 36.217],
#             [-98.392, 38.685],
#             [-86.594, 38.685],
#             [-86.594, 36.217],
#             [-98.392, 36.217]
#         ]
#     ]
# }
#
# gj = {
#     "type": "Polygon",
#     "coordinates": [
#         [
#             [-180, -90],
#             [-180, 90],
#             [180, 90],
#             [180, -90],
#             [-180, -90]
#         ]
#     ]
# }
# res = cdr.get_dedup_sites_search(
#     commodity='Copper',
#     bbox_polygon=json.dumps(bbox_polygon_site_search),
#     limit=1000
# )
# print(res)
# ranks = []
# for r in json.loads(res.to_json(orient='records')):
#     for k,v in r.items():
#         print(k,v)
#     #ranks.append(r['rank'])
#
# #print(list(set(ranks)))
# blerg
# # print(res)
# # commodities = {}
# # for r in res:
# #     c = r['mineral_inventory'][0]['commodity']
# #     if c not in commodities:
# #         commodities[c] = 0
# #     commodities[c] += 1
# #     cs = [x['commodity'] for x in r['mineral_inventory']]
# #     dts = [x['observed_name'] for x in r['deposit_type_candidate']]
# #     #print(r['deposit_type_candidate'])
# #     #print(len(r['mineral_inventory']),len(r['deposit_type_candidate']))
# #     #print(cs, dts)
# #     print(r['site_type'])
# #     #commodities.append()
# #     #rint()
# # print(len(res))
# # for c in sorted(commodities):
# #     print(c,commodities[c])
# #
# # print(r)
#
# # res = cdr.get_tiles_sources(page_size=1000)
# # systems = {}
# # for r in res:
# #     print()
# #     #for cog in r:
# #     #    print(cog)
# #     system = r['system']
# #     v = r['system_version']
# #     if system not in systems:
# #         systems[system] = []
# #     if v not in systems[system]:
# #         systems[system].append(v)
# #     #systems[sys]
# #     #print(r)
# #
# # for s in sorted(systems):
# #     print(s, systems[s])
#
# #print(len(res))
#
#
# res = cdr.get_prospectivity_data_sources()
# for r in res:
#     #if '12m' in r['data_source']['description']:# == 'tif':
#     #if 'evidence_layer_raster_prefix' in r['data_source']:
#     if '12mhack' in r['description']:
#         print(r['description'],r['data_source_id'])
    #print(list(r['data_source'].keys()))#['evidence_layer_raster_prefix'])


#print(cdr.get_polygons_by_sgmc_geology_major1('Sedimentary'))
#print(cdr.get_cog_count()) # <- returns "0" for some reason
#print(cdr.get_random_cog())
#print(cdr.get_cog_meta('224f073f05ff28f50cb72d774d37282f1b5f34df70e338c738e738f738e718a3'))
#print(cdr.get_cog_results('224f073f05ff28f50cb72d774d37282f1b5f34df70e338c738e738f738e718a3'))
#print(cdr.get_cog_info('224f073f05ff28f50cb72d774d37282f1b5f34df70e338c738e738f738e718a3'))

#resp = cdr.get_maps_list()
#for map in resp['maps']:
#    print()
#    print(map)

#print(cdr.get_deposit_types())
#print(cdr.get_commodity_list())
#print(cdr.get_mineral_site_grade_and_tonnage('copper'))
#print(cdr.get_mineral_site_deposit_type_classification_results('copper'))

#print(cdr.get_hyper_site_results('copper'))
#cdr.get_mineral_site_inventories('zinc').to_csv('/home/mgbillmi/PROCESSING/zinc_from_cdr.csv') # <- this one typically returns a huge file (>20 MB) and often times out


#print(cdr.get_mineral_site_deposit_type_candidates('Epithermal mercury'))
#print(cdr.get_mineral_site_deposit_type_candidates_csv('Epithermal mercury'))


preprocess_metadata = '''{
    "cma_id": "ESRI:102008_bdaf6346717f92613f3352615b6c616dab715b6c1d0674f91cf95e6a88f6a6fc__res0_500_res1_500_nickel",
    "system": "statmagic",
    "system_version": "0.0.1",
    "evidence_layers": [
        {
            "data_source_id": "Geophysics_Gravity_Bouguer_HGM_res0_211779_res1_211779_cat_LayerCategoryGEOPHYSICS",
            "title": "Geophysics_Gravity_Bouguer_HGM",
            "transform_methods": [
                "log",
                {
                    "impute_method": "mean",
                    "window_size": [
                        3,
                        3
                    ]
                }
            ],
            "label_raster": false
        },
        {
            "data_source_id": "Geophysics_Gravity_Bouguer_res0_211779_res1_211779_cat_LayerCategoryGEOPHYSICS",
            "title": "Geophysics_Gravity_Bouguer",
            "transform_methods": [],
            "label_raster": false
        }
    ],
    "vector_layers": [
        {
            "label_raster": true,
            "title": "Training sites",
            "evidence_features": [
                {
                    "raw_data_type": "mineral_site",
                    "id": "ffef1cfdf49b4a36aa192834e28ee72a"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "f730593b136147779cd1fbfb5f059de4"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "a801cdff0df64535ad824649315a4361"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "86e1b02328c2484cbbbc73e0b607c995"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "09e3afc9ebe9408d8828fa69ef661386"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "b780b8881cfc4db0a329a6e596862c08"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "f88d7ecdc3f4486f9b9f7d704f3d804a"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "f77c52122c2d4bd98a97d5a7b247e86b"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "ee0f597aaa62453c8830821e742ff115"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "ecbbebbdd51e4386bbd538e09f1b6fab"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "e3912ad36dca4ec3aaa904fb0c3950c6"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "aee22f48814e4ab8923a09f6519cf16f"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "ab6a08ba415d47fba37fde36be6cae84"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "9d1e01996ada409398683c9ad3f3fb47"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "992ba26c79e84196988b9b8dd2fd58db"
                },
                {
                    "raw_data_type": "mineral_site",
                    "id": "8baa6457789f448ca9bd42077624da5c"
                }
            ],
            "extra_geometries": [],
            "transform_methods": []
        }
    ]
}'''


#res = cdr.post_prospectivity_preprocess(preprocess_metadata)
#res = cdr.get_processed_data_layer_events('ESRI:102008_bdaf6346717f92613f3352615b6c616dab715b6c1d0674f91cf95e6a88f6a6fc__res0_500_res1_500_nickel')
#https://api.cdr.land/v1/prospectivity/event/bee5379f417c4da1ba318fbfd3296914
res = cdr.get_preprocess_event('bee5379f417c4da1ba318fbfd3296914')
#res = cdr.get_processed_data_layer('d7848f650d28fd995bca5cf4a27b3f18__4cf3b043a38f568cb6e598efc6f08508_f8ffc0b5fe885f8301c495763f5da851')
print(json.dumps(res,indent=4))