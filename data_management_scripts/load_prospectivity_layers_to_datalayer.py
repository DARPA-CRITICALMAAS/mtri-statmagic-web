import dm_util
from cdr import cdr_utils

con1 = dm_util.con1

### Pull layers from CDR
cdr = cdr_utils.CDR()
res = cdr.get_prospectivity_input_layers()

insert_start = '''
    INSERT INTO public.datalayer(
	    name, name_alt, description, source, path, category, subcategory, data_format)'
    VALUES('''

sql = ''
for r in res:
    if r['data_source']['format'] == 'tif':
        ds = r['data_source']

        name = ds['description'].replace(' ','_').replace('-','_').replace('(','').replace(')','')

        dl, created = dm_util.models.DataLayer.objects.get_or_create(
            name = name,
            defaults = {
                'name_alt': ds['description'],
                'description': ds['description'],
                'source': f"{','.join(ds['authors'])}. {ds['publication_date'].split('-')[0]}. {ds['description']}",
                'category': ds['category'].capitalize(),
                'subcategory': ds['subcategory'].capitalize().rstrip('s'),
                'path': r['file'],
            },
        )
        #dl.save()


