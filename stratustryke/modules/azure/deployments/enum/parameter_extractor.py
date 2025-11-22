from stratustryke.core.module.azure import AzureModule
from stratustryke.core.lib import module_data_dir
from stratustryke.core.credential import AZ_MGMT_TOKEN_SCOPE
import json
from pathlib import Path


class Module(AzureModule):

    OPT_DOWNLOAD_DIR = 'DOWNLOAD_DIR'
    OPT_PRINT_PARAMS = 'PRINT_PARAMS'

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
        self._options.add_boolean(Module.OPT_PRINT_PARAMS, 'When enabled, prints parameter values to framework output', True, True)
        self._options.add_string(Module.OPT_DOWNLOAD_DIR, 'When set, saves full deployment specification to the directory', False, None)

        
        self.auth_token = None

    
    @property
    def search_name(self):
        return f'azure/deployments/enum/{self.name}'
    

    def write_deployment_to_file(self, deployment_id: str, content: str) -> bool:
        '''Returns true|false if file write operation succeeeds'''

        download_dir = self.get_opt(Module.OPT_DOWNLOAD_DIR)
        if download_dir == None: return True

        # make sure our write directory exists
        filepath = Path(f'{download_dir}/{deployment_id}')
        filepath.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(filepath, 'w') as f: json.dump(content, f, indent=4)
            self.print_success(f'Wrote to {filepath}')
        except Exception as err:
            self.print_failure(f'Could not write to file: {deployment_id}')
            if self.verbose: self.print_error(str(err))
            return False
        
        return True
    

    def inspect_tenant_deployments(self) -> list:
        '''List tenant-level deployments'''

        ret = []
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = 'https://management.azure.com/providers/Microsoft.Resources/deployments/?api-version=2025-04-01'

        res = self.http_request('GET', endpoint, headers=headers)
        deployments = json.loads(res.text).get('value', [])
        # TODO: Logic to parse response for parameters!!
        ret = []
        for entry in deployments:
            try:

                deployment_id = entry.get('id', 'UNKNOWN')
                parameters = entry.get('properties', {}).get('parameters', [])

                if len(parameters.keys()) > 0:
                    self.print_status(f'Found parameters for {deployment_id}')

                for key in parameters.keys():
                    type = parameters[key].get('type', None)
                    val = parameters[key].get('value', None)

                    # if self.verbose and val != None:
                    
                    if self.get_opt(Module.OPT_PRINT_PARAMS): self.print_success(f'({type}) {key}: {val}')
                    ret.append(f'({type}) {key}: {val}')

                self.write_deployment_to_file(deployment_id, entry)

            except Exception as err:
                self.print_warning(f'Error inspecting deployments for {deployment_id}')
                if self.verbose: self.print_warning(str(err))
        
        if len(ret) < 1:
            self.print_failure('No tenant-level deployment parameters found')
        # for line in reportable:
        #     self.print_success(line)

        return ret


    def inspect_subscription_deployments(self, subscription: str) -> list:
        '''List subscription-level deployments within the target subscription'''

        ret = []
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = f'https://management.azure.com/subscriptions/{subscription}/providers/Microsoft.Resources/deployments/?api-version=2025-04-01'
        
        res = self.http_request('GET', endpoint, headers=headers)
        deployments = json.loads(res.text).get('value', [])

        # TODO: Logic to parse response for parameters!!

        for entry in deployments:
            try:
                deployment_id = entry.get('id', 'UNKNOWN')
                parameters = entry.get('properties', {}).get('parameters', {})
                
                if len(parameters.keys()) > 0:
                    self.print_status(f'Found parameters for {deployment_id}')

                for key in parameters.keys():
                    type = parameters[key].get('type', None)
                    val = parameters[key].get('value', None)

                    # if self.verbose and val != None:
                    
                    if self.get_opt(Module.OPT_PRINT_PARAMS): self.print_success(f'({type}) {key}: {val}')
                    ret.append(f'({type}) {key}: {val}')

                self.write_deployment_to_file(deployment_id, entry)

            except Exception as err:
                self.print_warning(f'Error inspecting deployments for {deployment_id}')
                if self.verbose: self.print_warning(str(err))

        if len(ret) < 1:
            self.print_failure(f'No subscription-level deployment parameters found')

        return ret
    

    def inspect_resource_group_deployments(self, subscription: str) -> list:
        '''List resource groups configured within the subscription and their deployments'''
        ret = []
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        group_ids = self.list_resource_groups(subscription)

        # Resource Group Id format is /subscriptions/SUBSCRIPTION_ID/resourceGroups/RESOURCE_GROU_NAME"
        if len(group_ids) < 1:
             self.print_failure(f'No resource-groups found in subscription {subscription}')
        else:
            self.print_status(f'Identified {len(group_ids)} resource groups in subscription {subscription}')

            for resource_group in group_ids:
                try:
                    endpoint = f'https://management.azure.com{resource_group}/providers/Microsoft.Resources/deployments/?api-version=2025-04-01'
                    res = self.http_request('GET', endpoint, headers=headers)
                    deployments = json.loads(res.text).get('value', [])
                    
                    # TODO: Logic to parse response for parameters!!
                    for entry in deployments:
                        deployment_id = entry.get('id', 'UNKNOWN')
                        parameters = entry.get('properties', {}).get('parameters', [])

                        if len(parameters.keys()) > 0:
                            self.print_status(f'Found parameters for {deployment_id}')

                        for key in parameters.keys():
                            type = parameters[key].get('type', None)
                            val = parameters[key].get('value', None)

                            # if self.verbose and val != None:
                            
                            if self.get_opt(Module.OPT_PRINT_PARAMS): self.print_success(f'({type}) {key}: {val}')
                            ret.append(f'({type}) {key}: {val}')

                        self.write_deployment_to_file(deployment_id, entry)

                except Exception as err:
                    self.print_warning(f'Couldn\'t list deployments in {resource_group}')
                    if self.verbose: self.print_warning(str(err))


        if len(ret) < 1:
            self.print_failure(f'No deployment parameters found at resource group scope')

        return ret
    


    def run(self) -> None:
        
        self.auth_token = self.get_cred().access_token(scope=AZ_MGMT_TOKEN_SCOPE)
        subscriptions = self.get_opt_az_subscription()

        self.print_status(f'Attempting to retrieve tenant-level deployment parameters...')
        ret = self.inspect_tenant_deployments()
        
        for subscription in subscriptions:
            self.print_status(f'Searching for deployment parameters in {subscription}')
            ret = self.inspect_subscription_deployments(subscription)
            ret = self.inspect_resource_group_deployments(subscription)

        return None

