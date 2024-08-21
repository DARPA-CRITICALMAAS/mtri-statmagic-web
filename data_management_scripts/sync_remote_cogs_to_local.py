import os, requests, shutil
import dm_util


dd = '/home/mgbillmi/PROCESSING/statmagic_datalayer_download/'
dd = f'/net/vm-apps2{dm_util.util.settings.TILESERVER_LOCAL_SYNC_FOLDER}'

# for datalayer in dm_util.getDataLayers():
for datalayer in dm_util.getOutputLayers():
    print(datalayer.download_url)

    ofile = os.path.join(dd,f'{datalayer.data_source_id}.tif')

    if not os.path.exists(ofile):
        bn = os.path.basename(datalayer.download_url)
        with requests.get(datalayer.download_url) as r:
            with open(ofile,'wb') as f:
                #print(r.content)
                f.write(r.content)

        # Compress and add overviews
        temp_tif = 'temp_compress.tif'
        cmd = f'gdal_translate -co "COMPRESS=LZW" -co "BIGTIFF=YES" {ofile} {temp_tif}'
        os.system(cmd)
        shutil.move(temp_tif, ofile)

        os.system(f'gdaladdo {ofile} 2 4 8 16')
