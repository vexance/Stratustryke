# Author: @vexance
# Purpose: Microsoft365 Modules to interact with M365 or Entra

from stratustryke.core.module.m365 import M365Module
from stratustryke.core.option import Options
from stratustryke.settings import AWS_DEFAULT_REGION
from stratustryke.core.lib import StratustrykeException
import typing
import stratustryke.core.credential
import json
from os import linesep
from http.client import responses as httpresponses
from requests import request, Response
from pathlib import Path
import urllib3


# Microsft modules to interact with azure subscriptions
class AzureModule(M365Module):

    OPT_AZ_SUBCRIPTION = 'AZ_SUBSCRIPTION'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._options.add_string(AzureModule.OPT_AZ_SUBCRIPTION, 'Target subscription id(s) (default: all accessible to principal) [S/F/P]', False)
        self.auth_token = None


    @property
    def search_name(self):
        return f'azure/{self.name}'
    

    def get_opt_az_subscription(self) -> list:
        '''Module built-in for common way to get subscription ids'''
        subscriptions = self.get_opt_multiline(AzureModule.OPT_AZ_SUBCRIPTION)


        if subscriptions == [] or subscriptions == None:
            subscriptions = []
            subs = self.list_subscriptions()
            for tenant, sub in subs:
                self.framework.print_status(f'Found accessible subscription {sub}')
                subscriptions.append(sub)
        
        if subscriptions == []: self.framework.print_warning('No subscriptions found')
        return subscriptions


    def list_tenants(self) -> list:
        '''List tenants acessible to the logged on user. Returns list<tuple(tenant_id, domain)>'''
        ret = []
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = 'https://management.azure.com/tenants?api-version=2022-12-01'

        res = self.http_request('GET', endpoint, headers=headers)
        tenants = json.loads(res.text).get('value', [])

        for entry in tenants:
            tenant_id = entry.get('tenantId', None)
            domain = entry.get('defaultDomain', None)

            if all([tenant_id, domain]): ret.append((tenant_id, domain))

        return ret
    

    def list_subscriptions(self) -> list:
        '''List subscriptions accessible to the logged on user. Returns list<tuple(tenant_id, subscription_id)>'''
        ret = []
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = 'https://management.azure.com/subscriptions?api-version=2022-12-01'

        res = self.http_request('GET', endpoint, headers=headers)
        if res.status_code != 200:
            self.framework.print_error(f'Error listing subscriptions: {res.text}')
            return []
        
        subscriptions = json.loads(res.text).get('value', [])

        for entry in subscriptions:
            tenant_id = entry.get('tenantId', None)
            sub_id = entry.get('subscriptionId', None)

            module_tenant = self.get_opt(M365Module.OPT_AUTH_TENANT)
            if module_tenant == None or module_tenant == tenant_id:
                if all([tenant_id, sub_id]): ret.append((tenant_id, sub_id))
            else:
                self.logger.debug(f'Skipping listing of subscription {sub_id} as it is not in the auth tenant')

        return ret
    

    def list_resource_groups(self, subscription: str) -> list:
        '''Returns the id for resource groups within the target subscription'''

        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = f'https://management.azure.com/subscriptions/{subscription}/resourcegroups?api-version=2022-09-01'

        res = self.http_request('GET', endpoint, headers=headers)
        resource_groups = json.loads(res.text).get('value', [])

        return [g.get('id', None) for g in resource_groups]

    
        
