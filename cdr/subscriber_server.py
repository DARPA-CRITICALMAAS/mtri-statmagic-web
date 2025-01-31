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
from subprocess import Popen, PIPE

# Import cdr_schemas
if 'CDR_SCHEMAS_DIRECTORY' in os.environ:
    sys.path.append(os.environ['CDR_SCHEMAS_DIRECTORY'])
else:
    sys.path.append('/usr/local/project/cdr_schemas')
    
from fastapi.security import APIKeyHeader
from fastapi import (BackgroundTasks, Depends, FastAPI, HTTPException, Request, status)
from cdr_schemas.events import Event
import subscriber_handlers

# Generate unique system_name id
res = Popen("echo beak_via_mtri_$(tr -dc A-Za-z0-9 </dev/urandom | head -c 13)", shell=True, stdout=PIPE)
# system_name = res.stdout.read().decode('utf-8').strip()
system_name = 'beak-mtri'

SETTINGS = {
    'system_name': system_name,
    'system_version': '0.0.1',#os.environ["SYSTEM_VERSION"],
    'user_api_token': os.environ["CDR_API_TOKEN"],
    'cdr_host': os.environ["CDR_API"],
    'local_port': 9999,#,int(os.environ["NGROK_PORT"]),
    'registration_id': "",
    'registration_secret': 'secret',#os.environ["CDR_HOST"],
    'callback_url': ""
}

# If callback_url not in env, get ngrok to give us an endpoint
if 'LISTENER_CALLBACK_URL' in os.environ:
    callback_url = os.environ['LISTENER_CALLBACK_URL']
else:
    listener = ngrok.forward(SETTINGS['local_port'], authtoken_from_env=True) # Forward the local port through ngrok and get a listener.
    callback_url = listener.url() + "/hook" # Set the callback URL to the ngrok URL plus "/hook".

SETTINGS['callback_url'] = callback_url


def clean_up():
    # delete our registered system at CDR on program end
    headers = {'Authorization': f'Bearer {SETTINGS["user_api_token"]}'} # Define the headers for the HTTP request. The 'Authorization' header is set to 'Bearer ' followed by the user API token.
    client = httpx.Client(follow_redirects=True) # Create an HTTP client that follows redirects.
    client.delete(f"{SETTINGS['cdr_host']}/user/me/register/{SETTINGS['registration_id']}", headers=headers) # Send a DELETE request to the CDR host to unregister the system. The URL is constructed from the CDR host URL, the registration ID, and some static parts. The headers defined earlier are passed to the request.

# register clean_up
atexit.register(clean_up)




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
                subscriber_handlers.run_ta3_pipeline(evt.payload['model_run_id'])
            case _:
                print("Nothing to do for event: %s", str(evt).split('event=')[1].split(' ')[0])

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

def get_registrations():
    headers = {'Authorization': f'Bearer {SETTINGS["user_api_token"]}'}
    client = httpx.Client(follow_redirects=True)
    r = client.get(f"{SETTINGS['cdr_host']}/user/me/registrations", headers=headers)
    return r.json()

def delete_registrations():
    headers = {'Authorization': f'Bearer {SETTINGS["user_api_token"]}'}
    client = httpx.Client(follow_redirects=True)
    registrations = get_registrations()

    if len(registrations) != 0:
        for reg in registrations:
            client.delete(f"{os.environ['CDR_API']}/user/me/register/{reg['id']}",headers=headers)  # Send a DELETE request to the CDR host to unregister the system. The URL is constructed from the CDR host URL, the registration ID, and some static parts. The headers defined earlier are passed to the request.

def register_system():
    """Register our system to the CDR using the server_settings"""

    # Get all registrations associated with MTRI's CDR token
    # Delete all registrations if they exist, then re-register
    reg_res = get_registrations()
    if len(reg_res) != 0:
        delete_registrations()

    #global server_settings
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
    headers = {'Authorization': f'Bearer {SETTINGS["user_api_token"]}'}
    client = httpx.Client(follow_redirects=True) # follow_redirects=True argument tells the client to automatically follow redirects

    r = client.post(f"{SETTINGS['cdr_host']}/user/me/register",
                    json=registration, headers=headers)

    print(r)
    # Log our registration_id such we can delete it when we close the program.
    SETTINGS['registration_id'] = r.json()["id"]


if __name__ == "__main__":
    #set_float32_matmul_precision('medium') # reduces floating point precision for computational efficiency
    print("Registering with CDR")
    register_system()
    print("Starting TA3 server")
    run()
