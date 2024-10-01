'''
This corrects a mistake in process_vector_for_mapfile that was downloading the
vectors to the stem name of download_url instead of using the data_source_id.
'''


import glob, os, shutil
from pathlib import Path
import dm_util

sd = '/net/vm-apps2/home/mgbillmi/statmagic/data/datalayer_download/'

for dl in dm_util.util.models.DataLayer.objects.filter(data_format='shp'):
    stem = Path(dl.download_url).stem
    dsid = dl.data_source_id
    print('\n',stem, dsid)

    shp = os.path.join(sd,f'{dsid}.shp')

    os.system(f'shptree {shp}')

    # # Find all files matching this stem
    # for f in sorted(glob.glob(f'{sd}{stem}*')):
    #     print(f, f.replace(stem,dsid))
    #     shutil.move(f, f.replace(stem,dsid))




