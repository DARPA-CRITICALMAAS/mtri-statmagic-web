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


# map of PG db ModelType name to cdr_schema
mmap = {
    'jataware_rf': prospectivity_models.RFUserOptions,
    'sri_NN': prospectivity_models.NeuralNetUserOptions,
    'beak_som': prospectivity_models.SOMTrainConfig,
    'beak_bnn': prospectivity_models.fastBNNUserOptions,
}

# Map from cdr_schemas type -> models.ProcessParameter.input_type, which indicates HTML input type
typemap = {
    'integer': 'number',
    'float': 'number',
    'number': 'number',
    'array': 'range_double',
    'boolean': 'checkbox',
}

#model_name = 'jataware_rf'

#################
# Sync model-level updates <- ***any changes will require migrations***


#################
# Sync object-level updates

for model_name, cdr_schema_obj in mmap.items():

    # Sync SOMTrainConfig -> ModelParameter table

    model = dm_util.models.ProspectivityModelType.objects.filter(name=model_name)[0]
    #print(model.id)
    #blerg

    existing_parameters = {}
    for p in dm_util.models.ProspectivityModelTypeParameter.objects.filter(model__name=model_name):
        existing_parameters[p.name] = p

    schema = cdr_schema_obj.model_json_schema()


    for prop,pobj in schema['properties'].items():
        print(prop,pobj)
        if prop not in existing_parameters:
            paramobj = dm_util.models.ProspectivityModelTypeParameter(
                name = prop,
                model = model,
                order=99,
            )
           # continue
        else:
            #if prop in existing_parameters:
            paramobj = existing_parameters[prop]

        name_pretty = input_type = options = description  = None
        html_attributes = {}

        update_fields = {}

        update_fields['optional'] = 'required' in schema and prop not in schema['required']

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