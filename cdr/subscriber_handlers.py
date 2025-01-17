import atexit, json, os, requests, shutil, sys, tempfile, urllib
from pathlib import Path
from beak.integration.statmagic.call_som import run_som
from beak.integration.statmagic.call_bnn import run_bnn

model_functions = {
    'beak_som': run_som,
    'beak_bnn': run_bnn,
}


# Import cdr_schemas
if 'CDR_SCHEMAS_DIRECTORY' in os.environ:
    sys.path.append(os.environ['CDR_SCHEMAS_DIRECTORY'])
else:
    sys.path.append('/usr/local/project/cdr_schemas')

import cdr_utils

def run_ta3_pipeline(model_run_id):
    datalayer_cache_dir = os.environ["DATALAYER_CACHE_DIR"]
    output_folder = None
    
    @atexit.register
    def exit():
        if output_folder and os.path.exists(output_folder):
            shutil.rmtree(output_folder)
    
    # Get model run metadata from CDR 
    print('Model run submission detected!',model_run_id)


    cdr = cdr_utils.CDR()
    res = cdr.get_model_run(model_run_id)
    
    # Ignore model runs unless they are 'beak_som' type
    model_type = res['event']['payload']['model_type']
    if model_type not in ('beak_som','beak_bnn'):
        print('\tNot Beak SOM type; ignoring...')
        return

    print('\n*************\nProcessing Beak model type: ',model_type)

    # Set temporary output folder                                                        
    output_folder = os.path.join('/tmp',res['model_run_id'])#Path('/tmp',res['model_run_id'])
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    #output_folder.mkdir(parents=True, exist_ok=True)      
        
    # Extract list of download_urls from the model run payload
    input_file_list = []
    input_labels = None
    for l in res['event']['payload']['evidence_layers']:
        pl = cdr.get_processed_data_layer(l['layer_id'])
        
        ext = pl['download_url'].split('.')[-1]
        
        download_file = os.path.join(datalayer_cache_dir,f"{l['layer_id']}.{ext}")
        
        if 'label_raster' in pl and pl['label_raster']: 
            input_labels = download_file
        else:
            input_file_list.append(download_file)  
            
        if os.path.exists(download_file):
            continue
        
        # Download file to temporary directory
        with requests.get(pl['download_url']) as r,open(download_file,'wb') as f:
            f.write(r.content)
    
    # Save json to temporary file b/c that's what run_som takes in
    with tempfile.NamedTemporaryFile() as tmpfile:
        config_file = tmpfile.name
        
    with open(config_file,'w') as f:
        f.write(json.dumps(res))
    
    # Would like the output from run_som to be a list of tuples
    # [(path_to_raster1, ProspectivityOutputLayer1), (path_to_raster2, ProspectivityOutputLayer2), ...]
    output_layers = model_functions[model_type](
        input_layers=input_file_list,
        input_labels=input_labels,
        config_file=config_file,
        output_folder=output_folder
    )

    for output_layer in output_layers:
        print(output_layer[0])
        print(output_layer[1].model_dump_json())
        
        meta = output_layer[1]#.model_dump_json()
        if meta.title == 'Codebook Map':
            bn = os.path.basename(output_layer[0]).split('.')[0][2:]
            meta.title = f'Codebook Map: {bn}'
        response = cdr.post_prospectivity_output_layers(
            input_file=open(output_layer[0],'rb'),
            metadata=output_layer[1].model_dump_json(),
        )
        print(response)
    
    #print(output_layers)
