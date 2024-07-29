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


    def run_query(self,query,csv=False):
        '''
        Queries a CDR API endpoint

        Parameters
        ----------
        query : str
            URL representing API endpoint including args, not including API
            server host name/version, e.g.
                'knowledge/csv/mineral_site_grade_and_tonnage/copper'

        csv : bool
            Indicates whether or not response is a CSV; if not, assumed to be
            JSON

        Returns
        -------
        response : dict OR pandas data frame
            API response which is either dict representing JSON or if csv=True,
            a pandas data frame representing CSV response
        '''
        resp = self.client.get(
            f'{self.cdr_host}/{self.cdr_version}/{query}',
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
    # TA2 "knowledge" endpoint convenience functions

    def get_list_deposit_types(self):
        return self.run_query('minerals/deposit-types')

    def get_mineral_sites_search(self, commodity='', candidate='NYF pegmatite', limit=10):
        return self.run_query(
            f'minerals/sites/search?candidate={candidate}&commodity={commodity}&limit={limit}'
        )

    def get_mineral_systems(self):
        return self.run_query('minerals/systems')

    #
    # def get_deposit_types(self):
    #     return self.run_query('knowledge/deposit_types')
    #
    #
    # def get_commodity_list(self):
    #     return self.run_query('knowledge/commodities')
    #
    #
    # def get_mineral_site_grade_and_tonnage(self,commodity):
    #     '''
    #
    #     Parameters
    #     ----------
    #     commodity : str
    #         name of commodity, e.g. 'copper'
    #
    #     Returns
    #     -------
    #     response : pandas dataframe
    #         represents CSV response from API
    #     '''
    #
    #     return self.run_query(
    #         f'knowledge/csv/mineral_site_grade_and_tonnage/{commodity}',
    #         csv=True
    #     )
    #
    #
    # def get_mineral_site_deposit_type_classification_results(self,commodity):
    #    return self.run_query(
    #        f'knowledge/csv/mineral_site_deposit_type_classificiation_results/{commodity}',
    #        csv=True
    #    )
    #
    #
    # def get_hyper_site_results(self,commodity):
    #     return self.run_query(
    #         f'knowledge/csv/hyper_site_results/{commodity}',
    #         csv=True
    #     )
    #
    #
    # def get_mineral_site_inventories(self,commodity):
    #     return self.run_query(
    #         f'knowledge/csv/mineral_site_inventories/{commodity}',
    #         csv=True
    #     )
    #
    #
    # def get_mineral_site_deposit_type_candidates(self,deposit_type_name):
    #     '''
    #
    #     Parameters
    #     ----------
    #     deposit_type_name : str
    #         deposit type name (see list of opts from get_deposit_types()), e.g.:
    #         "Epithermal mercury"
    #
    #     Returns
    #     -------
    #     response : pandas dataframe
    #         represents CSV results from API
    #     '''
    #     return self.run_query(
    #         f'knowledge/mineral_site_deposit_type_candidates/{deposit_type_name}'
    #     )
    #
    #
    # def get_mineral_site_deposit_type_candidates_csv(self, deposit_type_name):
    #     '''
    #     Parameters
    #     ----------
    #     deposit_type_name : str
    #         deposit type name (see list of opts from get_deposit_types()), e.g.:
    #         "Epithermal mercury"
    #
    #     Returns
    #     -------
    #     response : dict
    #         dict representing JSON response from API
    #     '''
    #     return self.run_query(
    #         f'knowledge/csv/mineral_site_deposit_type_candidates/{deposit_type_name}',
    #         csv=True
    #     )

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

    ####################################
    # Tiles
    def get_tiles_sources(self):
        return self.run_query(f'tiles/sources')

#
### Testing code...
cdr = CDR()
res = cdr.get_tiles_sources()

for r in res:
    print()
    #for cog in r:
    #    print(cog)
    print(r)
print(len(res))


# res = cdr.get_prospectivity_input_layers()
# for r in res:
#     if 'LAB' in r['data_source']['description']:# == 'tif':
#         print(r)


#print(cdr.get_polygons_by_sgmc_geology_major1('Sedimentary'))
#print(cdr.get_cog_count()) # <- returns "0" for some reason
#print(cdr.get_random_cog())
#print(cdr.get_cog_meta('224f073f05ff28f50cb72d774d37282f1b5f34df70e338c738e738f738e718a3'))
#print(cdr.get_cog_results('224f073f05ff28f50cb72d774d37282f1b5f34df70e338c738e738f738e718a3'))
#print(cdr.get_cog_info('224f073f05ff28f50cb72d774d37282f1b5f34df70e338c738e738f738e718a3'))

#resp = cdr.get_maps_list()
#for map in resp['maps']:
#    print()
#    print(map)

#print(cdr.get_deposit_types())
#print(cdr.get_commodity_list())
#print(cdr.get_mineral_site_grade_and_tonnage('copper'))
#print(cdr.get_mineral_site_deposit_type_classification_results('copper'))

#print(cdr.get_hyper_site_results('copper'))
#cdr.get_mineral_site_inventories('zinc').to_csv('/home/mgbillmi/PROCESSING/zinc_from_cdr.csv') # <- this one typically returns a huge file (>20 MB) and often times out


#print(cdr.get_mineral_site_deposit_type_candidates('Epithermal mercury'))
#print(cdr.get_mineral_site_deposit_type_candidates_csv('Epithermal mercury'))

