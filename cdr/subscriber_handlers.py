import os, sys
from beak.hmi_integration.call_som import run_som

# Import cdr_schemas
if 'CDR_SCHEMAS_DIRECTORY' in os.environ:
    sys.path.append(os.environ['CDR_SCHEMAS_DIRECTORY'])
else:
    sys.path.append('/usr/local/project/cdr_schemas')

import cdr_utils

def run_ta3_pipeline(model_run_id):
    
    # Get model run metadata from CDR 
    print('Model run submission detected!',model_run_id)
    
    res = cdr.get_model_run(model_run_id)
    
    # Ignore model runs unless they are 'beak_som' type
    if res['event']['payload']['model_type'] != 'beak_som':
        print('\tNot Beak SOM type; ignoring...')
    
    # Extract list of download_urls from the model run payload
    cdr = cdr_utils.CDR()
    input_file_list = []
    for layer_id in res['event']['payload']['evidence_layers']:
        pl = cdr.get_processed_data_layer(layer_id)
        input_file_list.append(pl['layer_id'])
    
    # Set temporary output folder
    output_folder = os.path.join('/tmp',res['model_run_id'])
    os.mkdir(output_folder)
    
    # Save json to temporary file b/c that's what run_som takes in
    with tempfile.NameTemporaryFile() as tmpfile:
        config_file = tmpfile.name
        
    with open(config_file,'w') as f:
        f.write(json.dumps(res))
    
    # Would like the output from run_som to be a list of tuples
    # [(path_to_raster1, ProspectivityOutputLayer1), (path_to_raster2, ProspectivityOutputLayer2), ...]
    output_layers = run_som(
        input_layers=input_file_list,
        config_file=config_file,
        output_folder=output_folder
    )
    print(output_layers)