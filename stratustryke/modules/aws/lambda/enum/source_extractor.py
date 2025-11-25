from stratustryke.core.module.aws import AWSModule
from pathlib import Path
from stratustryke.lib import module_data_dir
import requests
import urllib3

class Module(AWSModule):

    OPT_LAMBDA_PREFIX = 'LAMBDA_PREFIX'
    OPT_ALL_VERSIONS = 'ALL_VERSIONS'
    OPT_DOWNLOAD_DIR = 'DOWNLOAD_DIR'
    OPT_NO_DOWNLOAD = 'NO_DOWNLOAD'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Exfiltrate lambda source code from accessible functions',
            'Details': 'Describe lambda function(s), then attempts to use the caller\'s credentials to retrieve the source code for target functions or all functions if not supplied',
            'References': [ '' ]
        }

        self._options.add_string(Module.OPT_DOWNLOAD_DIR, 'Directory files will be downloaded to', True, module_data_dir(self.name))
        self._options.add_boolean(Module.OPT_NO_DOWNLOAD, 'When enabled, disables source code download and only enumerates configs', True, False)

        self._advanced.add_string(Module.OPT_LAMBDA_PREFIX, 'Prefix for lambdas to include (default: match ALL functions)', False)
        self._advanced.add_boolean(Module.OPT_ALL_VERSIONS, '(WORK IN PROGRESS) When enabled, attemmpts to insepect ALL unique function versions in history.')


    @property
    def search_name(self):
        return f'aws/lambda/enum/{self.name}'
    

    def list_lambdas(region: str, self) -> list:
        '''List lambdas in the region, return list of function names with the given prefix. If list operation fails, return ["LAMBDA_PREFIX"]'''
        session  = self.get_cred().session(region)
        lambdas = []

        prefix = self.get_opt(Module.OPT_LAMBDA_PREFIX)
        if prefix == None: prefix = ''

        try:
            client = session.client('lambda')

            paginator = client.get_paginator('list_functions')
            pages = paginator.paginate()


            for page in pages:
                funcs = page.get('Functions')
                for function in funcs:
                    arn = function.get('FunctionArn', None)
                    name = function.get('FunctionName', None)
                    envs = function.get('Environment', {}).get('Variables', None)
                    role = function.get('Role', None)
                    desc = function.get('Description', None)
                    version = function.get('Version', None)


                    if name.startswith(prefix):
                        lambdas.append(name)
                        self.print_success(f'Found {arn} ({version})')
                        
                        if self.verbose and role != None:
                            self.print_success(f'({name}) Execution Role: {role}')

                        if self.verbose and envs != None:
                            self.print_success(f'({name}) Environment Variables: {envs}')

                        if self.verbose and desc != None and desc != '':
                            self.print_success(f'({name}) Function Description: {desc}')


        except Exception as err:
            self.print_failure(f'Exception thrown during lambda:ListFunctions in {region}')
            if self.verbose: self.print_error(str(err))

            if lambdas == []:
                self.print_warning(f'Attempting to continue with source extraction for \'{prefix}\'')
                return [prefix]
            else:
                self.print_warning(f'Attempting to continue with {len(lambdas)} retrieved functions')
        
        return lambdas
    

    def get_presigned_url(self, region: str, name: str) -> str:
        '''Retrieve pre-signed URL for the lambda source'''
        presigned_url = None
        session = self.get_cred().session(region)

        try:
            client = session.client('lambda')
            res = client.get_function(FunctionName=name)
            presigned_url = res.get('Code', {}).get('Location')

        except Exception as err:
            self.print_failure(f'({name}) Exception thrown during lambda:GetFunction operation in {region}')
            if self.verbose: self.print_error(str(err))
            return None

        return presigned_url
    

    def download_source(self, region: str, name: str) -> bool:
        '''Perform download of source code from presigned URL'''
        s3_url = self.get_presigned_url(region, name)
        download_dir = self.get_opt(Module.OPT_DOWNLOAD_DIR)

        if self.get_opt(Module.OPT_NO_DOWNLOAD): return True

        try:
            # Make sure to conform to framework HTTP proxy settings
            HTTP_PROXY = self.web_proxies
            HTTP_VERIFY_SSL = self.framework._config.get_val(self.framework.CONF_HTTP_VERIFY_SSL)
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            res = requests.get(s3_url, stream=True, proxies=HTTP_PROXY, verify=HTTP_VERIFY_SSL)
            res.raise_for_status()

            download_path = str(Path(download_dir).resolve().absolute())
            
            with open(f'{download_path}/{name}.zip', 'wb') as file:
                for chunk in res.iter_content(chunk_size=8192):
                    file.write(chunk)

            self.print_success(f'Downloaded {download_path}/{name}.zip')

        except Exception as err:
            self.print_failure(f'({name}) Error downloading lambda source in {region}')
            if s3_url != None: self.print_warning(f'({name}) Pre-Signed URL: {s3_url}')
            if self.verbose: self.print_error(str(err))
            
            return False

        return True

    
    def run(self):

        for region in self.get_regions():
            matches = self.list_lambdas(region)
            self.print_status(f'Attempting to extract code for {len(matches)} function(s)...')

            for func in matches:
                self.download_source(region, func)

        return None
        