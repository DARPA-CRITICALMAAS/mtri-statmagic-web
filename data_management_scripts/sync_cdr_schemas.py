'''
Imports cdr_schemas and sync's them to the web GUI database

'''


import dm_util
from django.forms.models import model_to_dict

con1 = dm_util.con1

# Import cdr_schemas
import sys
sys.path.append('/usr/local/project/cdr_schemas/')
from cdr_schemas import prospectivity_models

# Map from cdr_schemas type -> models.ProcessParameter.input_type, which indicates HTML input type
typemap = {
    'integer': 'number',
    'float': 'number',
    'number': 'number',
}

#################
# Sync model-level updates <- ***any changes will require migrations***







#################
# Sync object-level updates

# Sync SOMTrainConfig -> ModelParameter table

existing_parameters = {}
for p in dm_util.models.ModelParameter.objects.filter(model__name='beak_som'):
    existing_parameters[p.name] = p

schema = prospectivity_models.SOMTrainConfig.model_json_schema()
#print(schema.keys())
#print(schema['$defs'])

for prop,pobj in schema['properties'].items():
    print(prop,pobj)
    if prop not in existing_parameters:
        continue

    #if prop in existing_parameters:
    paramobj = existing_parameters[prop]

    name_pretty = input_type = options = description  = None
    html_attributes = {}

    update_fields = {}

    update_fields['optional'] = prop not in schema['required']

    # Get prop type
    if 'anyOf' in pobj:
        ptype = pobj['anyOf'][0]
    elif 'type' in pobj:
        ptype = pobj['type']
    else:
        print('What the type for this one?\n',prop,pobj)
        sys.exit(1)
    if 'type' in ptype:
        input_type = typemap[ptype['type']]
    elif '$ref' in ptype:
        ref = ptype['$ref'].split('/')[-1]

        update_fields['input_type'] = 'select'
        #print(ptype['$ref'])
        update_fields['options'] = schema['$defs'][ref]['enum']

    # Get other parameters
    if 'default' in pobj:
        html_attributes['value'] = pobj['default']

    if ptype == 'integer':
        html_attributes['step'] = 1

    if 'title' in pobj:
        update_fields['name_pretty'] = pobj['title']

    if 'description' in pobj:
        update_fields['description'] = pobj['description']

    # Update the model instance
    for field,value in update_fields.items():
        if value and value != getattr(paramobj,field):
            setattr(paramobj,field,value)

    # html_attributes is a special case b/c we just want to update the
    # individual keys that are updated, NOT replace the whole JSON dict
    for attr,v in html_attributes.items():
        print(attr,v)
        if paramobj.html_attributes is None:
            paramobj.html_attributes = {}
        paramobj.html_attributes[attr] = v

    print('Updating: ',update_fields)

    # Save updates to the instance
    paramobj.save()




#
# print()
#
# print(schema['required'])
# print(schema['title'])
# print(schema['type'])
# print(schema['$defs'])
# Sync NeuralNetUserOptions -> ModelParameter table