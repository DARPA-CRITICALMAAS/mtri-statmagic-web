import os, requests
import dm_util


dd = '/home/mgbillmi/PROCESSING/statmagic_datalayer_download/'

for datalayer in dm_util.getDataLayers():
    print(datalayer.path)

    bn = os.path.basename(datalayer.path)
    with requests.get(datalayer.path) as r:
        with open(os.path.join(dd,bn),'wb') as f:
            #print(r.content)
            f.write(r.content)