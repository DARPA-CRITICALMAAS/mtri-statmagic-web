import os
import tempfile
import json
from pathlib import Path
#from tqdm import tqdm
from typing import List, Dict

import sys

# CDR intergration imports
import atexit
import hashlib
import hmac
import httpx
import ngrok
import uvicorn
import uvicorn.logging
import optuna

# Import cdr_schemas
if 'CDR_SCHEMAS_DIRECTORY' in os.environ:
    sys.path.append(os.environ['CDR_SCHEMAS_DIRECTORY'])
else:
    sys.path.append('/usr/local/project/cdr_schemas')

current = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(current)))
from cdr import cdr_utils

from fastapi.security import APIKeyHeader
from fastapi import (BackgroundTasks, Depends, FastAPI, HTTPException, Request, status)
from cdr_schemas.events import Event

#from beak.hmi_integration.call_som import run_som

# SRI TA3 specific imports
#from torch import set_float32_matmul_precision

SETTINGS = {
    'system_name': 'beak_via_mtri',#os.environ["SYSTEM_NAME"],
    'system_version': '0.0.1',#os.environ["SYSTEM_VERSION"],
    #'ml_model_name': '',#os.environ["MODEL_NAME"],
    #'ml_model_version': os.environ["MODEL_VERSION"],
    'user_api_token': os.environ["CDR_TOKEN"],
    'cdr_host': 'https://api.cdr.land',#os.environ["CDR_HOST"],
    'local_port': 9999,#,int(os.environ["NGROK_PORT"]),
    'registration_id': "",
    'registration_secret': 'https://api.cdr.land',# os.environ["CDR_HOST"],
    'callback_url':""
}


def run_ta3_pipeline(model_run_id):
    
    # Get model run metadata from CDR 
    print('Model run submission detected!',model_run_id)
    
    res = cdr.get_model_run(model_run_id)
    
    if res['event']['payload']['model_type'] != 'beak_som':
        print('\tNot Beak SOM type; ignoring...')
    
    with tempfile.NameTemporaryFile() as tmpfile:
        config_file = tmpfile.name
        
    with open(config_file,'w') as f:
        f.write(json.dumps(res))
    #train_config =

    # Would like the output from run_som to be a list of tuples
    # [(path_to_raster1, ProspectivityOutputLayer1), (path_to_raster2, ProspectivityOutputLayer2), ...]
    output_layers = run_som(
        input_layers=input_file_list,
        config_file=config_file,
        output_folder=output_folder
    )

def run_ta3_pipeline_orig(
        event_id: int,
        app_settings: dict
    ):
    
    print("Querying CDR for event.")
    model_event_json = utils.get_event_payload_result(id=event_id, app_settings=app_settings)

    print("Parsing CDR event payload.")
    model_event_obj = utils.parse_event_payload_result(model_event_json)

    print("Generating AOI geopackage.")
    aoi_geopkg_path = utils.create_aoi_geopkg(model_event_obj)

    print("Downloading reference layer (aka template_raster.tif).")
    reference_layer_path = utils.download_reference_layer(model_event_obj)

    print("Downloading deposits.")
    deposits_path = utils.download_deposits(model_event_obj, app_settings=app_settings)

    print("Processing label raster.")
    processed_label_raster_path, number_of_deposits = preprocessing.process_label_raster(
        event_obj=model_event_obj,
        deposits_csv_path=deposits_path,
        aoi=aoi_geopkg_path,
        reference_layer_path=reference_layer_path
    )
    print(f"The number of fully rasterized deposits is: {number_of_deposits}")

    print("Downloading evidence layers.")
    evidence_layer_paths = utils.download_evidence_layers(model_event_obj)

    print("Preprocessing evidence layers.")
    processed_evidence_layer_paths = preprocessing.preprocess_evidence_layers(
        event_obj=model_event_obj,
        layers=evidence_layer_paths,
        aoi=aoi_geopkg_path,
        reference_layer_path=reference_layer_path
    )

    print("Creating a raster stack.")
    raster_stack_path = preprocessing.generate_raster_stack(
        evidence_layer_paths=processed_evidence_layer_paths,
        label_raster_path=processed_label_raster_path
    )

    print("Creating raster stack .yaml file.")
    raster_stack_yaml_path = preprocessing.create_raster_stack_yaml(
        event_obj=model_event_obj,
        evidence_layer_paths=processed_evidence_layer_paths,
        label_raster_path=processed_label_raster_path,
        raster_stack_path=raster_stack_path
    )

    print("Pretraining MAE.")
    pretrain_cfg = utils.build_hydra_config_notebook(
        overrides=[
            "experiment=pretrain_template.yaml",
            f"preprocess.raster_stacks.0.raster_stack_path={str(raster_stack_path)}",
            f"preprocess.raster_stacks.0.evidence_layer_paths={[str(layer_path) for layer_path in processed_evidence_layer_paths]}",
            f"preprocess.raster_stacks.0.label_raster_path={[str(processed_label_raster_path)]}",
            # "logger=csv", # wandb logger has issues in notebooks
            f"logger.wandb.name=pretrain|{str(model_event_obj.cma.mineral)}|{str(model_event_obj.model_run_id)}",
            f"tags=['pretrain','mae','ViT',{str(model_event_obj.model_run_id)},{str(model_event_obj.cma.mineral)}]",
            f"task_name=pretrain-{str(model_event_obj.cma.mineral)}-{str(model_event_obj.model_run_id)}",
            f"data.tif_dir={raster_stack_path.parent}",
            "data.batch_size=256",
            f"model.net.input_dim={len(processed_evidence_layer_paths)}",
            "paths.data_dir=data",
            "paths.log_dir=logs",
            "trainer=gpu",
            "trainer.min_epochs=1",
            "trainer.max_epochs=10",
        ]
    )
    utils.print_config_tree(pretrain_cfg)
    pretrain_metrics, pretrain_objs = pretrain(pretrain_cfg)

    print("Preparing classifier overrides")
    backbone_ckpt_embeddings = pretrain_objs['trainer'].checkpoint_callback.dirpath+f"/embeddings_d{pretrain_cfg.model.net.enc_dim}.npy"

    fixed_overrides = [
        "experiment=classifier_template.yaml",
        f"preprocess.raster_stacks.0.raster_stack_path={str(raster_stack_path)}",
        f"preprocess.raster_stacks.0.evidence_layer_paths={[str(layer_path) for layer_path in processed_evidence_layer_paths]}",
        f"preprocess.raster_stacks.0.label_raster_path={[str(processed_label_raster_path)]}",
        # "logger=csv",
        f"logger.wandb.name=train|{str(model_event_obj.cma.mineral)}|{str(model_event_obj.model_run_id)}",
        "paths.data_dir=data",
        "paths.log_dir=logs",
        f"task_name=train-{str(model_event_obj.cma.mineral)}-{str(model_event_obj.model_run_id)}",
        f"tags=['train','mae','ViT','frozen',{str(model_event_obj.model_run_id)},{str(model_event_obj.cma.mineral)}]",
        # trainer args
        "trainer=gpu",
        "trainer.min_epochs=10",
        "trainer.max_epochs=50",
        # data args
        f"data.tif_dir={raster_stack_path.parent}",
        f"data.frac_train_split=0.8", #{model_event_obj.train_config.fraction_train_split}",
        f"data.multiplier=20", #{model_event_obj.train_config.upsample_multiplier}",
        f"data.batch_size={32 if number_of_deposits < 50 else 128 if number_of_deposits > 100 else 64}",
        # model args
        f"model.net.backbone_net.input_dim={len(processed_evidence_layer_paths)}",
        f"model.net.backbone_ckpt_embeddings={backbone_ckpt_embeddings}",
        f"model.optimizer.lr=1e-3", #{model_event_obj.train_config.learning_rate}",
        f"model.optimizer.weight_decay=1e-2", #{model_event_obj.train_config.weight_decay}",
    ]
    # fixed_overrides = [
    #     "experiment=classifier_template.yaml",
    #     f"preprocess.raster_stacks.0.raster_stack_path={str(raster_stack_path)}",
    #     f"preprocess.raster_stacks.0.evidence_layer_paths={[str(layer_path) for layer_path in processed_evidence_layer_paths]}",
    #     f"preprocess.raster_stacks.0.label_raster_path={[str(processed_label_raster_path)]}",
    #     "logger=csv",
    #     f"logger.wandb.name=train|{str(model_event_obj.cma.mineral)}|{str(model_event_obj.model_run_id)}",
    #     "paths.data_dir=data",
    #     "paths.log_dir=logs",
    #     f"task_name=train-{str(model_event_obj.cma.mineral)}-{str(model_event_obj.model_run_id)}",
    #     f"tags=['train','mae','ViT','frozen',{str(model_event_obj.model_run_id)},{str(model_event_obj.cma.mineral)}]",
    #     # trainer args
    #     "trainer=gpu",
    #     "trainer.min_epochs=10",
    #     "trainer.max_epochs=50",
    #     # data args
    #     f"data.tif_dir={raster_stack_path.parent}",
    #     f"data.batch_size={32 if number_of_deposits < 50 else 128 if number_of_deposits > 100 else 64}",
    #     # model args
    #     f"model.net.backbone_net.input_dim={len(processed_evidence_layer_paths)}",
    #     f"model.net.backbone_ckpt_embeddings={backbone_ckpt_embeddings}",
    # ] # - after schemas get updated

    exposed_params_dict = model_event_obj.train_config.__dict__
    exposed_overrides = []
    optuna_params_dict = {}
    for key, value in exposed_params_dict.items():
        if key == "smoothing":
            if value:
                exposed_overrides.append(f"model.smoothing={model_event_obj.train_config.smoothing}")
            else:
                optuna_params_dict[key] = lambda x: f"model.smoothing={x}"
        elif key == "dropout":
            if value:
                exposed_overrides.append(f"model.net.dropout_rate=[0.0,{model_event_obj.train_config.dropout},{model_event_obj.train_config.dropout}]")
            else:
                optuna_params_dict[key] = lambda x: f"model.net.dropout_rate=[0.0,{x},{x}]"
        elif key == "negative_sampling_fraction":
            if value:
                exposed_overrides.append(f"data.likely_neg_range={list(model_event_obj.train_config.negative_sampling_fraction)}")
            else:
                optuna_params_dict[key] = lambda x,y: f"data.likely_neg_range={[x,y]}"
        else:
            raise ValueError(f"Unexpected key: {key}")

        # if key == "fraction_train_split":
        #     if value:
        #         exposed_overrides.append(f"data.frac_train_split={model_event_obj.train_config.fraction_train_split}")
        #     else:
        #         optuna_params_dict[key] = lambda x: f"data.frac_train_split={x}"
        # elif key == "upsample_multiplier":
        #     if value:
        #         exposed_overrides.append(f"data.multiplier={model_event_obj.train_config.upsample_multiplier}")
        #     else:
        #         optuna_params_dict[key] = lambda x: f"data.multiplier={x}"
        # elif key == "learning_rate":
        #     if value:
        #         exposed_overrides.append(f"model.optimizer.lr={model_event_obj.train_config.learning_rate}")
        #     else:
        #         optuna_params_dict[key] = lambda x: f"model.optimizer.lr={x}"
        # elif key == "weight_decay":
        #     if value:
        #         exposed_overrides.append(f"model.optimizer.weight_decay={model_event_obj.train_config.weight_decay}")
        #     else:
        #         optuna_params_dict[key] = lambda x: f"model.optimizer.weight_decay={x}"
        # elif key == "smoothing":
        #     if value:
        #         exposed_overrides.append(f"model.smoothing={model_event_obj.train_config.smoothing}")
        #     else:
        #         optuna_params_dict[key] = lambda x: f"model.smoothing={x}"
        # elif key == "likely_negative_range":
        #     if value:
        #         exposed_overrides.append(f"data.likely_neg_range={list(model_event_obj.train_config.likely_negative_range)}")
        #     else:
        #         optuna_params_dict[key] = lambda x,y: f"data.likely_neg_range={[x,y]}"
        # elif key == "dropout":
        #     if value:
        #         exposed_overrides.append(f"model.net.dropout_rate={list(model_event_obj.train_config.dropout)}")
        #     else:
        #         optuna_params_dict[key] = lambda x,y,z: f"model.net.dropout_rate={[x,y,z]}"
        # else:
        #     raise ValueError(f"Unexpected key: {key}")
        # # - after schemas get updated

    # add exposed (user provided) train configs (no optuna)
    fixed_overrides += exposed_overrides

    if len(optuna_params_dict) > 0:
        print(f"Running hyperparameter search for params: {list(optuna_params_dict.keys())}")
        optuna_overrides, optuna_trial = utils.run_optuna_study(fixed_overrides, optuna_params_dict)
        fixed_overrides += optuna_overrides

    print("Training classifier using pretrained MAE.")
    train_cfg = utils.build_hydra_config_notebook(overrides=fixed_overrides)
    utils.print_config_tree(train_cfg)
    train_metrics, train_objs = train(train_cfg)
    train_cfg.ckpt_path = train_objs["trainer"].checkpoint_callback.best_model_path

    print("Generating maps.")
    train_cfg.data.batch_size=128
    output_map_paths, _ = build_map(train_cfg)
    output_map_paths.sort(reverse=True) # place Uncertainties.tif first
    output_map_paths = [Path(path) for path in output_map_paths]

    print("Uploading results to CDR.")
    for path in tqdm(output_map_paths):
        utils.send_output(
            output_type=path.stem,
            output_path=path,
            payload=model_event_obj,
            app_settings=app_settings
        )

    print("Uploading processed evidence layers to CDR.")
    for evidence_layer_idx, path in tqdm(enumerate(processed_evidence_layer_paths)):
        utils.send_processed_evidence_layer(
            layer_path=path,
            layer=model_event_obj.evidence_layers[evidence_layer_idx],
            payload=model_event_obj,
            app_settings=app_settings
        )

    print(f"event_id={event_id} cma is finished!")




def clean_up():
    # delete our registered system at CDR on program end
    headers = {'Authorization': f'Bearer {SETTINGS["user_api_token"]}'} # Define the headers for the HTTP request. The 'Authorization' header is set to 'Bearer ' followed by the user API token.
    client = httpx.Client(follow_redirects=True) # Create an HTTP client that follows redirects.
    client.delete(f"{SETTINGS['cdr_host']}/user/me/register/{SETTINGS['registration_id']}", headers=headers) # Send a DELETE request to the CDR host to unregister the system. The URL is constructed from the CDR host URL, the registration ID, and some static parts. The headers defined earlier are passed to the request.

# register clean_up
atexit.register(clean_up)


# Get ngrok to give us an endpoint
listener = ngrok.forward(SETTINGS['local_port'], authtoken_from_env=True) # Forward the local port through ngrok and get a listener.
SETTINGS['callback_url'] = listener.url() + "/hook" # Set the callback URL to the ngrok URL plus "/hook".


app = FastAPI() # creating an instance


async def event_handler(
        evt: Event
    ):
    try:
        match evt: # pattern matching on evt.
            case Event(event="ping"):
                print("Received PING!")
            case Event(event="prospectivity_model_run.process"):
                print("Received model run event payload!")
                print(evt.payload)
                run_ta3_pipeline(evt.payload['model_run_id'])
            case _:
                print("Nothing to do for event: %s", evt)

    except Exception:
        print("background processing event: %s", evt)
        raise

# verify the signature of  a request
async def verify_signature(
    request: Request,
    signature_header: str = Depends(APIKeyHeader(name="x-cdr-signature-256"))
):
    payload_body = await request.body() # retrieving the body of the request
    if not signature_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="x-hub-signature-256 header is missing!")
    hash_object = hmac.new(
        SETTINGS['registration_secret'].encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256
    ) # creating a new hmac hash object
    expected_signature = hash_object.hexdigest() # calculating the hexadecimal digest
    # Compare the expected signature with the signature in the header
    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Request signatures didn't match!")
    return True


@app.post("/hook") # This decorator tells FastAPI to use this function (named hook) to handle POST requests to the "/hook" endpoint.
async def hook(
    evt: Event,
    background_tasks: BackgroundTasks, # a class provided by FastAPI that allows to add background tasks that will be run after returning the response.
    request: Request,
    verified_signature: bool = Depends(verify_signature),
):
    """Our main entry point for CDR calls"""

    background_tasks.add_task(event_handler, evt) # add a background task that will call the event_handler with evt as an argument
    return {"ok": "success"}


def run():
    """Run our web hook"""
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=SETTINGS['local_port'],
        reload=False
    ) # start a Uvicorn server with the FastAPI application


def register_system():
    """Register our system to the CDR using the server_settings"""
    #global server_settings
    headers = {'Authorization': f'Bearer {SETTINGS["user_api_token"]}'}

    registration = {
        "name": SETTINGS['system_name'],
        "version": SETTINGS['system_version'],
        "callback_url": SETTINGS['callback_url'],
        "webhook_secret": SETTINGS['registration_secret'],
        # Leave blank if callback url has no auth requirement
        "auth_header": "",
        "auth_token": "",
        # Registers for ALL events
        "events": []

    }
    # creating an httpx client
    client = httpx.Client(follow_redirects=True) # follow_redirects=True argument tells the client to automatically follow redirects

    r = client.post(f"{SETTINGS['cdr_host']}/user/me/register",
                    json=registration, headers=headers)

    # Log our registration_id such we can delete it when we close the program.
    SETTINGS['registration_id'] = r.json()["id"]


if __name__ == "__main__":
    #set_float32_matmul_precision('medium') # reduces floating point precision for computational efficiency
    print("Registering with CDR")
    register_system()
    print("Starting TA3 server")
    run()
