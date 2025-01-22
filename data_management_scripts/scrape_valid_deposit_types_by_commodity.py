import json
import urllib.parse
from cdr import cdr_utils


gj = {
    'type': 'Polygon',
    'coordinates': ((
        (-180,0),
        (180,0),
        (180,90),
        (-180,90),
        (-180,0)

        # (-78.50593, 6.664608), (-77.001544, 8.407168),
        # (-76.273124, 13.581921), (-60.522853, 11.544616),
        # (-44.950799, 51.179343), (-75.787818, 75.845169),
        # (-72.028561, 79.496652), (-57.270212, 83.026219),
        # (-167.606439, 83.753911), (-169.011996, 64.320872),
        # (-173.137277, 63.587675), (-187.786318, 54.316523),
        # (-188.752638, 51.179343), (-87.527109, 4.65308),
        # (-78.50593, 6.664608)
    ),)
}


# Initialize CDR client
cdr = cdr_utils.CDR()
cs = cdr.get_mineral_dedupsite_commodities()

dts_json = {}
for j,c in enumerate(sorted(cs)):
    if c == 'Stone, Crushed/Broken':
       continue

    #print(c)
    args = {
        'commodity': c,#urllib.parse.quote_plus(c),
        'with_deposit_types_only': True,
        'top_n': 1,
        'limit': -1,
        'bbox_polygon': json.dumps(gj)
    }

    sites_df = cdr.get_dedup_sites_search(**args)
    print(c,len(sites_df))

    dts = []
    pname = 'top1_deposit_type'
    for i,site in sites_df.iterrows():
        if pname in site and site[pname] not in dts and site[pname] not in [float('nan')]:
            dts.append(site[pname])

    dts_json[c] = sorted(dts)
    #print(dts)
    #blerg


print(json.dumps(dts_json,indent=4))