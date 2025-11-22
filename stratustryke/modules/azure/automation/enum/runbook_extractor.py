
import json

from pathlib import Path

from stratustryke.core.credential.microsoft import AZ_MGMT_TOKEN_SCOPE
from stratustryke.core.module.azure import AzureModule
from stratustryke.lib import module_data_dir


class Module(AzureModule):

    OPT_DOWNLOAD_DIR = 'DOWNLOAD_DIR'
    OPT_DOWNLOAD_SRC = 'DOWNLOAD_SRC'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Exfiltrate automation runbook contents from automation accounts',
            'Details': 'Downloads accessible automation runbook source code to the local device',
            'References': [ 'https://github.com/vexance/RunbookExporter' ]
        }

        # self._options.add_string('ACCOUNT_PREFIX', 'Prefix for automation accounts to inclde (default: ALL) [S/F/P]')
        # self._options.add_string('RUNBOOK_PREFIX', 'Prefix for runbooks to include (default: ALL) [S/F/P]', False)
        self._options.add_string(Module.OPT_DOWNLOAD_DIR, 'Directory files will be downloaded to', True, module_data_dir(self.name))
        self._options.add_boolean(Module.OPT_DOWNLOAD_SRC, 'When enabled, enables source code download as well as config enum', True, True)
        
        self.auth_token = None

    
    @property
    def search_name(self):
        return f'azure/automation/enum/{self.name}'
    

    def list_automation_accounts(self, subscription: str) -> list:
        '''List automation accounts within a given subscription'''

        ret = []
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = f'https://management.azure.com/subscriptions/{subscription}/providers/Microsoft.Automation/automationAccounts?api-version=2023-11-01'

        res = self.http_request('GET', endpoint, headers=headers)
        accounts = json.loads(res.text).get('value', [])

        
        for entry in accounts:
            account_id = entry.get('id', None)
            if account_id != None: ret.append(account_id)

        return res.status_code, ret
    

    def list_runbooks(self, account_path: str) -> list:
        '''List automation runbooks configured within an automation account'''

        ret = []
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = f'https://management.azure.com{account_path}/runbooks?api-version=2023-11-01'

        res = self.http_request('GET', endpoint, headers=headers)
        runbooks = json.loads(res.text).get('value', [])

        for entry in runbooks:
            runbook_id = entry.get('id', None)
            if runbook_id != None: ret.append(runbook_id)

        return ret


    def get_runbook_metadata(self, runbook_path: str) -> None:
        '''Retrieve target automation runbook metadata'''
        
        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = f'https://management.azure.com{runbook_path}?api-version=2023-11-01'

        res = self.http_request('GET', endpoint, headers=headers)
        metadata = json.loads(res.text)

        name = metadata.get('name', None)
        tags = metadata.get('tags', {})
        desc = metadata.get('properties', {}).get('description', '')
        params = metadata.get('properties', {}).get('parameters', {})

        if tags != {}:   self.print_status(f'{name} Tags: {tags}')
        if params != {}: self.print_status(f'{name} Parameters: {params}')
        if desc != '':   self.print_status(f'{name} Description: {desc}')

        return None
    

    def get_runbook_content(self, runbook_path: str) -> tuple:
        '''Download runbook content and save to the designated download directory'''

        headers = {'Authorization': f'Bearer {self.auth_token}'}
        endpoint = f'https://management.azure.com{runbook_path}/content?api-version=2023-11-01'

        res = self.http_request('GET', endpoint, headers=headers)

        status = res.status_code
        content = res.text
        extension = self.interpret_extension(res.headers.get('Content-Type', 'UNKNOWN'))

        return (status, content, extension)


    def interpret_extension(self, content_type: str) -> str:
        '''Attempt to interpret the runbook file extension based off the content-type response header'''

        language = content_type[content_type.rfind('/')::].lower()

        ext = 'txt'
        if 'powershell' in language: ext = 'ps1'
        elif 'python' in language: ext = 'py'
        elif 'script' in language: ext = 'sh'
        else: self.logger.warn(f'Could not interpret runbook file extension from Content-Type {content_type}')

        return ext


    def run(self):

        self.auth_token = self.get_cred().access_token(scope=AZ_MGMT_TOKEN_SCOPE)
        subscriptions = self.get_opt_az_subscription()        

        download = self.get_opt(Module.OPT_DOWNLOAD_SRC)
        download_dir = self.get_opt(Module.OPT_DOWNLOAD_DIR)
        download_path = str(Path(download_dir).resolve().absolute())
        # account_prefixes = self.get_opt_multiline('ACCOUNT_PREFIX')
        # runbook_prefixes = self.get_opt_multiline('RUNBOOK_PREFIX')

        for subscription in subscriptions:

            self.print_status(f'Retrieving automation accounts within subscription {subscription}')
            
            status, accounts = self.list_automation_accounts(subscription)

            if status != 200:
                if status == 401:
                    self.print_failure(f'[{status} Response] Not authorized to list accounts in this subscription')
                elif status == 404:
                    self.print_warning(f'[{status} Response] Subscription not found, skipping')
                else: self.print_failure(f'[{status} Response] Unable to list automation accounts')
                continue

            if len(accounts) > 0:
                self.print_status(f'Searching for runbooks within {len(accounts)} automation accounts')
            else: self.print_warning(f'[{status} Response] No automation accounts found in {subscription}')

            for account_path in accounts:
                runbooks = self.list_runbooks(account_path)

                for runbook_path in runbooks:

                    self.print_success(runbook_path)
                    if self.verbose: self.get_runbook_metadata(runbook_path)
                    if download: 
                        status, content, extension = self.get_runbook_content(runbook_path)

                        if status != 200:
                            if status == 401:
                                self.print_failure(f'[{status} Response] Not authorized to retrieve runbook content')
                            else: self.print_failure(f'[{status} Response] Unable to download runbook content')
                        
                        else:
                            name_start = runbook_path.rfind('/')
                            name_end = runbook_path.find('?')
                            name = runbook_path[name_start:name_end]
                            
                            try:
                                with open(f'{download_path}/{name}.{extension}', 'w') as file:
                                    file.write(content)
                                self.print_success(f'Downloaded to {download_path}/{subscription}-{name}.{extension}')

                            except Exception as err:
                                self.print_error(f'Error writing runbook to disk: {err}')
                                
        return None




        
    

