import os, pidfile, sys, zipfile
from io import BytesIO
from urllib.request import urlopen
current = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(current))
import dm_util

outputlayers = dm_util.models.OutputLayer.objects.filter().order_by('category','subcategory','name')

for dl in outputlayers:
    # print()
    ext = dl.download_url.split('.')[-1]
    data_format = ext
    if ext == 'zip':
        print(dl.data_format,dl.download_url)

        resp = urlopen(dl.download_url)

        # Open zipfile
        try:
            myzip = zipfile.ZipFile(BytesIO(resp.read()))

        except:
            print(
                f'Problem opening zipfile: date_source_id={dl.data_source_id}; download_url={dl.download_url}')
            continue

        for f in myzip.namelist():
            if '.shp' in f:
                print('shp!!!')
                data_format = 'shp'
                break

        dl.data_format = data_format
        dl.save()