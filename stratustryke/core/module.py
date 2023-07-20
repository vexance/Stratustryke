# Author: @vexance
# Purpose: Base class definitions for AWS, Azure, and GCP class modules

from stratustryke.core.option import Options
from stratustryke.settings import AWS_DEFAULT_REGION
import typing
import stratustryke.core.credential
from os import linesep


class StratustrykeModule(object):
    def __init__(self, framework) -> None:
        self.framework = framework
        self._info = { # set to false here to verify authors put this info in
            'Authors': False, # list[str} Authors who wrote the module
            'Details': False, # str detailed explanation of what the module does
            'Description': False, # str brief (one-line) summary of what module does
            'References': False # list[str] External references pertaining to the module
        }
        self._options = Options()

    @property
    def desc(self) -> str:
        return self._info.get('Description', 'Unknown')

    @property
    def logger(self):
        return self.framework.get_module_logger(self.name)

    @property
    def path(self) -> str:
        return self.__module__.split('.', 3)[-1].replace('.', '/')

    @property
    def name(self) -> str:
        return self.path.split('/')[-1]

    @property
    def search_name(self) -> str:
        return f'generic/{self.name}'

    def show_options(self, mask: bool = False, truncate: bool = True) -> list:
        ''':return: list[list[str]] containing rows of column values'''
        return self._options.show_options(mask, truncate)


    def validate_options(self) -> tuple:
        '''Validate option-specific requirements.
        :rtype: (bool, str | None)'''
        # Wrapper for Options class validate_options() call; can be overriden for additional checks
        return self._options.validate_options()


    def load_strings(self, file: str) -> list:
        ''':return: list[str] | None'''
        try:
            with open(file, 'r') as handle:
                return [line.strip(f'{linesep}') for line in handle.readlines()]
        
        except Exception as err:
            self.framework.print_error(f'Error reading contents of file: {file}')
            return None


    def show_info(self) -> list:
        '''Return module information and technical details. Should not be overriden in child classes
        :rtype: list<str>'''
        output = []
        output.append(f'  Module Name: {self.search_name}')
        output.append(f'  Author(s): {", ".join(self._info.get("Authors", []))}')
        
        output.append(f'  References:')
        for ref in self._info.get('References', []):
            output.append(f'  -  {ref}')
        
        output.append(f'  Description: {self.desc}')
        output.append(f'  Details:')
        output.append(f'    {self._info.get("Details", "UNKNOWN")}')

        return output


    def get_opt(self, name: str) -> typing.Any:
        '''Return the current value for the option; Pass to Options.get_val() NOTE: returns value, not the option object'''
        return self._options.get_val(name)


    def set_opt(self, name: str, val: typing.Any) -> None:
        '''Sets the value for the option; Pass to Options.set_opt()'''
        self._options.set_opt(name, val)


    def unset_opt(self, name: str) -> None:
        '''Sets value for the option to None; Pass to Options.unset_opt()'''
        self._options.unset_opt(name)


    def reset_opt(self, name: str) -> None:
        '''Reset value to default for the option; Pass to Options.reset_opt()'''
        self._options.reset_opt(name)


#    Must be implemented by grandchild / child classes
#    def run(self) -> None:
#        '''Execute current module. This serves as the Module\'s main() function. This will automatically trigger option validation when set in the stratustryke config.'''
#        pass



class AWSModule(StratustrykeModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._options.add_string('AUTH_ACCESS_KEY_ID', 'AWS access key id for authentication', True, regex = '(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}')
        self._options.add_string('AUTH_SECRET_KEY', 'AWS secret key to use for authentication', True, regex='[0-9a-zA-Z\/+]{40}', sensitive=True)
        self._options.add_string('AUTH_SESSION_TOKEN', 'AWS session token for temporary credential authentication', regex='[0-9a-zA-Z\/+]{364}', sensitive=True)
        self._options.add_string('AWS_REGION', 'AWS region to specify within calls', False, AWS_DEFAULT_REGION)
        self._cred = None
    
    def validate_options(self) -> tuple:
        # Validate required params and regex matches
        valid, msg = super().validate_options()
        if not valid:
            return (valid, msg)

        # Temporary creds (from STS service 'ASIA...') require a session token
        key_prefix = self.get_opt('AUTH_ACCESS_KEY_ID')[0:3]
        token = self.get_opt('AUTH_SESSION_TOKEN')
        if ((token == '' or token == None)  and key_prefix in ['ASIA']):
            return (False, f'Session token required for temporary STS credential \'{self.auth_access_key_id.value}\'')

        # Looks good
        return (True, None)


    def get_cred(self, region: str = None):
        access_key = self.get_opt('AUTH_ACCESS_KEY_ID')
        secret = self.get_opt('AUTH_SECRET_KEY')
        token = self.get_opt('AUTH_SESSION_TOKEN')
        cred_region = region if (region != None) else self.get_opt('AWS_REGION')

        return stratustryke.core.credential.AWSCredential(f'{self.name}', access_key=access_key, secret_key=secret, session_token=token, default_region=cred_region)


    @property
    def search_name(self):
        return f'aws/{self.name}'


# Todo:
class AzureModule(StratustrykeModule):
    def __init__(self) -> None:
        super().__init__()
        

# Todo
class GCPModule(StratustrykeModule):
    def __init__(self) -> None:
        super().__init__()
