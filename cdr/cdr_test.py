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
#
# res = cdr.get_model_run('ba7010d52a8744c1b6e36df69922d5b0')
# print(res)
# blerg
#
# res = cdr.intersect_sources(json.dumps(post_data_intersect_sources))
# #res = cdr.get_cmas()
# print(res)
# print(len(res))
# print(res[0].keys())
#print(cdr.get_mineral_inventories('copper'))

bbox_polygon_site_search = {
    # "bbox": [
    #     36.217,
    #     -88.392,
    #     38.685,
    #     -86.594
    # ],
    "type": "Polygon",
    "coordinates": [
        (
            [-88.392,36.217],
            [-88.392,38.685],
            [-86.594,38.685],
            [-86.594,36.217],
            [-88.392,36.217]
        )
    ]
}

# res = cdr.get_mineral_sites_search(
#     commodity='Rare earth elements',
#     candidate='',
#     bbox_polygon=json.dumps(bbox_polygon_site_search),
#     limit=-1
# )
# print(res)
# commodities = {}
# for r in res:
#     c = r['mineral_inventory'][0]['commodity']
#     if c not in commodities:
#         commodities[c] = 0
#     commodities[c] += 1
#     cs = [x['commodity'] for x in r['mineral_inventory']]
#     dts = [x['observed_name'] for x in r['deposit_type_candidate']]
#     #print(r['deposit_type_candidate'])
#     #print(len(r['mineral_inventory']),len(r['deposit_type_candidate']))
#     #print(cs, dts)
#     print(r['site_type'])
#     #commodities.append()
#     #rint()
# print(len(res))
# for c in sorted(commodities):
#     print(c,commodities[c])
#
# print(r)

res = cdr.get_tiles_sources(page_size=1000)
systems = {}
for r in res:
    print()
    #for cog in r:
    #    print(cog)
    system = r['system']
    v = r['system_version']
    if system not in systems:
        systems[system] = []
    if v not in systems[system]:
        systems[system].append(v)
    #systems[sys]
    #print(r)

for s in sorted(systems):
    print(s, systems[s])

#print(len(res))


# res = cdr.get_prospectivity_input_layers()
# for r in res:
#     if 'LAB' in r['data_source']['description']:# == 'tif':
#         print(r)


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
