import dm_util

download_url = 'https://s3.amazonaws.com/public.cdr.land/prospectivity/inputs/52023649c9ec4c4fbd7d90e797383937.zip'

ds = dm_util.models.DataLayer.objects.filter(download_url=download_url)[0]

dm_util.util.process_vector_for_mapfile(ds)