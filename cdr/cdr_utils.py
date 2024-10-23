import httpx
import json
import os
import pandas as pd
import io

class CDR():
    '''
    Class with utils for interfacing with the CDR

    '''

    def __init__ (
            self,
            cdr_host = "https://api.cdr.land",
            cdr_version = 'v1'
        ):
        '''
        On initialization, register authentication headers and httpx client

        Parameters
        ----------
        cdr_host : str
            URL of the CDR API server

        cdr_version : str
            CDR version string, which is part of the API call; e.g. 'v1'


        '''

        self.cdr_host = cdr_host
        self.cdr_version = cdr_version

        # Retrieve CDR API token from env variables
        token = os.environ['CDR_API_TOKEN']

        self.headers = {"Authorization": f"Bearer {token}"}
        self.client = httpx.Client(follow_redirects=True)

        # Set an extended timeout period b/c the CSV endpoints in particular
        # take longer than the default of 5 seconds
        self.timeout_seconds = 60000


    def run_query(self,query,csv=False,POST=False,files=None):
        '''
        Queries a CDR API endpoint

        Parameters
        ----------
        query : str
            URL representing API endpoint including args, not including API
            server host name/version, e.g.
                'knowledge/csv/mineral_site_grade_and_tonnage/copper'

        POST : dict
            For POST requests, the variable is a dict representing the 'data'
            arg input to the httpx.post() function

        csv : bool
            Indicates whether or not response is a CSV; if not, assumed to be
            JSON

        Returns
        -------
        response : dict OR pandas data frame
            API response which is either dict representing JSON or if csv=True,
            a pandas data frame representing CSV response
        '''
        if POST:
            headers = self.headers
            # headers['Content-Type'] = 'application/json'
            resp = self.client.post(
                f'{self.cdr_host}/{self.cdr_version}/{query}',
                data = POST,
                files=files,
                headers=headers,
                timeout=self.timeout_seconds
            )
        else:
            url = f'{self.cdr_host}/{self.cdr_version}/{query}'
            print(url)
            resp = self.client.get(
                url,
                headers=self.headers,
                timeout=self.timeout_seconds
            )

        # Raises error if not success
        # Alternatively, could check for success and log, e.g.:
        # if not resp.is_success:
        #       logger.exception(f'Query not successful; reason: {resp.content}')
        # ...or could wrap the below "raise" call in try/except and log result
        resp.raise_for_status()

        # If not a CSV response, assume JSON
        if csv:
            data = self.process_csv_result(resp.content)
        else:
            data = resp.json()

        return data


    def process_csv_result(self, content_bytes):
        '''
        Processes a CSV response from CDR endpoint; expects "content_bytes"

        Parameters
        ----------
        content_bytes bytes
            'content' attribute of a response object from httpx to CDR API
            endpoint that returns a CSV

        Returns
        -------
        response : pandas dataframe
            Represents CSV response from API
        '''

        return pd.read_csv(io.BytesIO(content_bytes))

    ####################################
    # TA2 "mineral" endpoint convenience functions

    def get_list_deposit_types(self):
        return self.run_query('minerals/deposit-types')


    def get_dedup_sites_search(
            self,
            commodity='',
            with_deposit_types_only='false',
            system='',
            system_version='',
            top_n=1,
            bbox_polygon='',
            limit=10
        ):
        '''

        :param commodity: (optional) should be capitalized, e.g. Iron, Zinc
        :param candidate:  (optional)
        :param bbox_polygon:
        :param limit:
        :return:
        '''
        return self.run_query(
            f'minerals/dedup-site/search/{commodity}?top_n={top_n}&with_deposit_types_only={with_deposit_types_only}&limit={limit}',
            POST=bbox_polygon,
            csv = True,
        )

    def get_mineral_systems(self):
        return self.run_query('minerals/systems')

    def get_mineral_inventories(self, commodity):
        return self.run_query(f'minerals/inventories/{commodity}')


    def get_mineral_dedupsite_commodities(self):
        return self.run_query('minerals/dedup-site/commodities')

    ####################################
    # TA1 "maps" endpoint convenience functions

    def get_cog_count(self):
        return self.run_query(f'maps/cog/count')

    def get_random_cog(self, georeferenced='false'):
        return self.run_query(
            f'maps/cog/random?georeferenced={georeferenced}'
        )

    def get_cog_meta(self, cog_id):
        return self.run_query(
            f'maps/cog/meta/{cog_id}'
        )

    def get_cog_results(self, cog_id):
        return self.run_query(
            f'maps/cog/{cog_id}/results'
        )

    def get_cog_info(self, cog_id):
        return self.run_query(
            f'maps/cog/{cog_id}'
        )

    def get_polygons_by_sgmc_geology_major1(self,Major1):
        '''
        See "LITH1" column here for valid "Major1" values:
        https://pubs.usgs.gov/ds/1052/ds20171052_appendix4.pdf

            Sedimentary
            Igneous
            Metamorphic
            Tectonite
            Unconsolidated

        '''
        return self.run_query(
            f'maps/search/sgmc_geology?smgc_geology_major_1={Major1}'
        )

    def get_maps_list(self, size=10, page=0):
        return self.run_query(
            f'maps/list?size={size}&page={page}'
        )

    ####################################
    # Prospectivity
    def get_prospectivity_input_layers(self):
        return self.run_query(
            f'prospectivity/input/layers'
        )

    def get_prospectivity_data_sources(self,page=0,size=1000):
        return self.run_query(
            f'prospectivity/data_sources?page={page}&size={size}'
        )

    def post_prospectivity_data_source(self,input_file,metadata):
        '''

        :param input_file: (str) path to input file
        :param metadata: (str) JSON model dump
        :return:
        '''
        return self.run_query(
            f'prospectivity/datasource',
            POST={'metadata': metadata},
            files={'input_file': input_file}
        )

    def get_prospectivity_output_layers(self,cma_id='',page=0,size=10000,model_run_id=''):
        return self.run_query(
            f'prospectivity/prospectivity_output_layers?page={page}&size={size}&cma_id={cma_id}&model_run_id={model_run_id}'
        )

    def post_cma(self, input_file, metadata):
        return self.run_query(
            f'prospectivity/cma',
            POST={'metadata': metadata},
            files={'input_file': input_file}
        )

    def get_cma(self, cma_id):
        return self.run_query(
            f'prospectivity/cma?cma_id={cma_id}'
        )

    def get_cmas(self, page=0,size=1000,search_text=''):
        return self.run_query(
            f'prospectivity/cmas?page={page}&size={size}&search_text={search_text}'
        )

    def get_model_run(self, model_run_id):
        return self.run_query(
            f'prospectivity/model_run?model_run_id={model_run_id}'
        )

    def get_model_runs(self, cma_id, size=10000):
        return self.run_query(
            f'prospectivity/model_runs?cma_id={cma_id}&size={size}'
        )

    def post_model_run(self,metadata):
        return self.run_query(
            'prospectivity/prospectivity_model_run',POST=metadata
        )

    def post_prospectivity_preprocess(self, metadata):
        return self.run_query(
            'prospectivity/prospectivity_preprocess', POST=metadata
        )

    def get_processed_data_layer_events(self,cma_id=''):
        return self.run_query(
            f'prospectivity/processed_data_layer_events?cma_id={cma_id}'
        )

    def get_processed_data_layers(self,event_id=''):
        return self.run_query(
            f'prospectivity/processed_data_layers?event_id={event_id}'
        )

    def get_processed_data_layer(self,layer_id):
        return self.run_query(
            f'prospectivity/processed_data_layer?layer_id={layer_id}'
        )

    def get_preprocess_event(self,event_id):
        return self.run_query(
            f'prospectivity/event/{event_id}'
        )

    ####################################
    # Tiles
    def get_tiles_sources(self,page_size=10):
        return self.run_query(f'tiles/sources?page_size={page_size}')

    def intersect_sources(self,post_data):
        return self.run_query(
            'tiles/intersect_sources',
            POST=post_data
        )


