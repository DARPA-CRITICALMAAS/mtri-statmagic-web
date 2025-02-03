# Adding a new model type to StatMaGIC

## 1. Add new model type to StatMaGIC

This step can completed either through the StatMaGIC admin console (available at: \[insert_usgs_statmagic_host\]/admin]), or by using an INSERT query within a statmagic database session.

If logged into the **admin** console:
* Click on `Prospectivity model types` in the table under `CMA` on the left
* Then click `ADD PROSPECTIVITY MODEL TYPE`
* Fill out the form:
    * `Name`: a unique identifier, no special characters; this will be used as the `model_type` parameter in the CDR model run submission request, and it will be used to link the the model type to the set of options specified in `cdr_schemas`
    * `Name pretty`: this is the text that will be displayed on StatMaGIC in the `Model type` dropdown selector.
    * `Description`: help text describing the model
    * `Uses database`: this should be checked
    * `Uses training`: check if you are adding a **supervised** model
    * (the remaining fields are optional; the `buttons` field is deprecated and can be ignored)


## 2. Add schema for model parameters

Create a new **class** that represents the set of parameters the user should be able to modify within the StatMaGIC interface. This should be created in the [./cdr_schemas/cdr_schemas/prospectivity_models.py](https://github.com/DARPA-CRITICALMAAS/cdr_schemas/blob/main/cdr_schemas/prospectivity_models.py) file. Use the [SOMTrainConfig](https://github.com/DARPA-CRITICALMAAS/cdr_schemas/blob/main/cdr_schemas/prospectivity_models.py#L72) as a template.

Once complete, the created schemas needs to be sync'd with the StatMaGIC database.
* Open [./mtri-statmagic-web/data_management_scripts/sync_cdr_schemas.py](https://github.com/DARPA-CRITICALMAAS/mtri-statmagic-web/blob/main/data_management_scripts/sync_cdr_schemas.py)
* Add the reference to the schema just created to the `mmap` variable at the top. The key you are adding should be the same as the StatMaGIC model type `Name` added in the previous step, and the value should be the **class** you just added to `cdr_schemas`. 
* Save and run the `sync_cdr_schemas.py` script within the StatMaGIC virtual environment
* Go into the StatMaGIC admin console (available at: \[insert_usgs_statmagic_host\]/admin]) and check the `Prospectivity model type parameters` table to see if the parameters loaded successfully. Adjust the `order` parameters are display (lower numbers = displayed first) here, as well as any group headers if certain parameters should be displayed under a common heading.
* At the point, you should be able to go to StatMaGIC, select the new model type from the dropdown list, and edit its configuration.


## 3. Add hooks in backend model submission code

In the [./mtri-statmagic-web/cma/views.py:submit_model_run](https://github.com/DARPA-CRITICALMAAS/mtri-statmagic-web/blob/main/cma/views.py#L872) function, update the `model_map` variable to include the model type you just created; as when editing the `mmap` variable in the [sync_cdr_schemas.py](https://github.com/DARPA-CRITICALMAAS/mtri-statmagic-web/blob/main/data_management_scripts/sync_cdr_schemas.py) script, the key should be the value for `name` you used when creating the `prospectivity model type` in **Step 1**, and the value should be the options **class** in [./cdr_schemas/cdr_schemas/prospectivity_models.py](https://github.com/DARPA-CRITICALMAAS/cdr_schemas/blob/main/cdr_schemas/prospectivity_models.py) created in the previous step.


## 4. Set up a CDR subscriber for processing model run submissions.

You can now submit model runs for the new model type in StatMaGIC, and you should receive a "Model run submitted successfully!" message, but no results will be returned because a subscriber and handler has not yet been set up to process the requests.

To do this, use the [./mtri-statmagic-web/cdr/subscriber_server.py](https://github.com/DARPA-CRITICALMAAS/mtri-statmagic-web/blob/main/cdr/subscriber_server.py) and [./mtri-statmagic-web/cdr/subscriber_handler.py](https://github.com/DARPA-CRITICALMAAS/mtri-statmagic-web/blob/main/cdr/subscriber_handler.py) scripts as templates to create a new listener.

The `subscriber_server.py` script registers the listener with the CDR and sends the request to the appropriate handler. 

The `subscriber_handlers.py` script parses the model configuration inputs received from StatMaGIC, runs the model, and posts the results to the CDR.
