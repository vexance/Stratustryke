# Author: @vexance
# Purpose: Microsoft365 Modules to interact with M365 or Entra

from stratustryke.core.module.microsoft import MicrosoftModule


AZ_MGMT_REST_URL='https://management.azure.com'


# Microsft modules to interact with azure subscriptions
class AzureModule(MicrosoftModule):

    OPT_AZ_SUBCRIPTION = 'AZ_SUBSCRIPTION'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._options.add_string(AzureModule.OPT_AZ_SUBCRIPTION, 'Target subscription id(s) (default: all accessible to principal) [S/F/P]', False)
        self.auth_token = None


    @property
    def search_name(self):
        return f'azure/{self.name}'
    

    def get_subscriptions(self) -> list:
        '''Module built-in for common way to get subscription ids'''
        subscriptions = self.get_opt_multiline(AzureModule.OPT_AZ_SUBCRIPTION)

        if subscriptions == [] or subscriptions == None:
            subscriptions = [] # make sure it is a list if it is in fact NoneType
            for tenant, sub in self.list_subscriptions():
                self.print_status(f'Found subscription {sub}')
                subscriptions.append(sub)
        
        if len(subscriptions) < 1: self.print_warning('No subscriptions found')
        return subscriptions
    

    def az_rest_get(self, path: str, version: str, headers: dict = {}) -> tuple[dict | str, int]:
        '''
        Utility function to call azure management REST APIs via the GET method
        :param path: REST API Path
        :param version: api-version query string value
        :param headers: Additional headers not including Authorization token
        :return: tuple[dict|str response, response status code]
        '''

        # Build endpoint URL; basic check for query string
        if not path.startswith('/'): path = f'/{path}'
        query_char = '?' if '?' not in path else '&' 
        endpoint = f'{AZ_MGMT_REST_URL}{path}{query_char}api-version={version}'


        # Determine request headers
        request_headers = {'Authorization': f'Bearer {self.auth_token}'}
        request_headers = request_headers | headers # merge the two dicts; explict auth headers will overwrite default

        try:
            res = self.http_request('GET', endpoint, headers=request_headers)

            try:
                res_body = res.json()
            except Exception as err:
                res_body = str(res.text)

            return res_body, res.status_code
        
        except Exception as err:
            error = res.content if res.content else str(err)
            status = res.status_code if res.status_code else -1
            return error, status


    def az_rest_request(self, method: str, path: str, version: str, headers: dict = {}, body = str|dict) -> tuple[dict | str, int]:
        '''
        Utility function to call azure management REST APIs via the GET method
        :param method: POST, PUT, DELETE, etc.
        :param path: REST API Path
        :param version: api-version query string value
        :param headers: Additional headers not including Authorization token
        :param body: string or dict(JSON) request body
        :return: tuple[dict|str response, response status code]
        '''

        # Build endpoint URL; basic check for query string
        if not path.startswith('/'): path = f'/{path}'
        query_char = '?' if '?' not in path else '&' 
        endpoint = f'{AZ_MGMT_REST_URL}{path}{query_char}api-version={version}'


        # Determine request headers
        request_headers = {'Authorization': f'Bearer {self.auth_token}'}
        request_headers = request_headers | headers # merge the two dicts; explict auth headers will overwrite default


        # Determine request body; if for some reason its bytes, we'll cast to string
        if isinstance(body, bytes):
            body = bytes.decode()
        if isinstance(body, str):
            req_data = body
            req_json = None
        elif isinstance(body, dict):
            req_data = None
            req_json = body
        else:
            msg = f'Unsupported request body ({type(body)}) is not a string or dictionary'
            self.print_error(msg)
            if self.verbose: self.print_error(f'Unsupported body contents: {body}')
            return msg, -1

        try:
            res = self.http_request(method, endpoint, headers=request_headers, data = req_data, json = req_json)

            try:
                res_body = res.json()
            except Exception as err:
                res_body = str(res.text)

            return res_body, res.status_code
        
        except Exception as err:
            error = res.content if res.content else str(err)
            status = res.status_code if res.status_code else -1
            return error, status


    def list_tenants(self) -> list:
        '''List tenants acessible to the logged on user. Returns list<tuple(tenant_id, domain)>'''
        body, status = self.az_rest_get('/tenants', '2022-12-01')

        if status != 200:
            self.print_failure(f'Failed to list tenants')
            if self.verbose:
                self.print_failure(f'[Status {status}] {body}')
            return []

        ret = []
        for entry in body:
            tenant_id = entry.get('tenantId', None)
            domain = entry.get('defaultDomain', None)

            if all([tenant_id, domain]): ret.append((tenant_id, domain))
            
        return ret
    

    def list_subscriptions(self) -> list:
        '''List subscriptions accessible to the logged on user. Returns list<tuple(tenant_id, subscription_id)>'''
        body, status = self.az_rest_get('/subscriptions', '2022-12-01')

        if status != 200:
            self.print_failure(f'Failed to list subscriptions')
            if self.verbose:
                self.print_failure(f'[Status {status}] {body}')
            return []
        
        ret = []
        for entry in body:
            tenant_id = entry.get('tenantId', None)
            sub_id = entry.get('subscriptionId', None)

            module_tenant = self.get_opt(MicrosoftModule.OPT_AUTH_TENANT)
            if module_tenant == None or module_tenant == tenant_id:
                if all([tenant_id, sub_id]): ret.append((tenant_id, sub_id))
            else:
                self.logger.debug(f'Skipping listing of subscription {sub_id} as it is not in the auth tenant')

        return ret
    

    def list_resource_groups(self, subscription: str) -> list:
        '''Returns the id for resource groups within the target subscription'''
        body, status = self.az_rest_get(f'/subscriptions/{subscription}/resourcegroups', '2022-09-01')

        if status != 200:
            self.print_failure(f'Failed to list resource groups in subscription {subscription}')
            if self.verbose:
                self.print_failure(f'[Status {status}] {body}')
            return []

        return [g.get('id', None) for g in body]

    
    