# Author: @vexance
# Purpose: Modules to interact with AWS cloud resources / services

from stratustryke.core.module import StratustrykeModule
from stratustryke.settings import AWS_DEFAULT_REGION, AWS_DEFAULT_ENABLED_REGIONS
from stratustryke.core.credential.aws import AWSCredential


class AWSModule(StratustrykeModule):


    OPT_ACCESS_KEY = 'AUTH_ACCESS_KEY_ID'
    OPT_SECRET_KEY = 'AUTH_SECRET_KEY'
    OPT_SESSION_TOKEN = 'AUTH_SESSION_TOKEN'
    OPT_AWS_REGION = 'AWS_REGION'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._options.add_string(AWSModule.OPT_ACCESS_KEY, 'AWS access key id for authentication', True, regex = '(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}')
        self._options.add_string(AWSModule.OPT_SECRET_KEY, 'AWS secret key to use for authentication', True, regex='[0-9a-zA-Z\\/+]{40}', sensitive=True)
        self._options.add_string(AWSModule.OPT_SESSION_TOKEN, 'AWS session token for temporary credential authentication', regex='[0-9a-zA-Z\\/+]{364}', sensitive=True)
        self._options.add_string(AWSModule.OPT_AWS_REGION, 'AWS region(s) to specify within calls', False, AWS_DEFAULT_REGION)
        self._cred = None


    @property
    def search_name(self):
        return f'aws/{self.name}'
    

    def validate_options(self) -> tuple:
        # Validate required params and regex matches
        valid, msg = super().validate_options()
        if not valid:
            return (valid, msg)

        # Temporary creds (from STS service 'ASIA...') require a session token
        key_prefix = self.get_opt(AWSModule.OPT_ACCESS_KEY)[0:3]
        token = self.get_opt(AWSModule.OPT_SESSION_TOKEN)
        if ((token == '' or token == None)  and key_prefix in ['ASIA']):
            return (False, f'Session token required for temporary STS credential \'{self.auth_access_key_id.value}\'')

        # Looks good
        return (True, None)


    def get_cred(self, region: str = None):
        access_key = self.get_opt(AWSModule.OPT_ACCESS_KEY)
        secret = self.get_opt(AWSModule.OPT_SECRET_KEY)
        token = self.get_opt(AWSModule.OPT_SESSION_TOKEN)
        cred_region = region if (region != None) else self.get_opt(AWSModule.OPT_AWS_REGION)

        return AWSCredential(self.name, access_key=access_key, secret_key=secret, session_token=token, default_region=cred_region)
        

    def get_regions(self) -> list[str]:
        '''Return the list of regions to run the module in'''
        regions = self.get_opt_multiline(AWSModule.OPT_AWS_REGION)
        if len(regions) == 1:
            if regions == [AWS_DEFAULT_REGION] or regions == None:
                regions = AWS_DEFAULT_ENABLED_REGIONS

        # Do we need to do input validation? For now leaving as-is
        return regions

