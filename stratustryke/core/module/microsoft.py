# Author: @vexance
# Purpose: Microsoft365 Modules to interact with M365 or Entra

from pathlib import Path

from stratustryke.core.module import StratustrykeModule
from stratustryke.core.credential.microsoft import MicrosoftCredential


class MicrosoftModule(StratustrykeModule):

    OPT_AUTH_TOKEN = 'AUTH_TOKEN'
    OPT_AUTH_PRINCIPAL = 'AUTH_PRINCIPAL'
    OPT_AUTH_SECRET = 'AUTH_SECRET'
    OPT_AUTH_TENANT = 'AUTH_TENANT'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._options.add_string(MicrosoftModule.OPT_AUTH_TOKEN, 'Existing access token or refresh token; overrides other AUTH_* options', False, sensitive=True)
        self._options.add_string(MicrosoftModule.OPT_AUTH_PRINCIPAL, 'Entra service principal id, email, or managed identity', False)
        self._options.add_string(MicrosoftModule.OPT_AUTH_SECRET, 'Authentication secret (e.g, client secret / password)', False, sensitive=True)
        self._options.add_string(MicrosoftModule.OPT_AUTH_TENANT, 'Azure tenant / directory identifer; required if AUTH_TOKEN not set', False, regex='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
        self._cred = None


    @property
    def search_name(self):
        return f'm365/{self.name}'
    

    def get_cred(self):
        refresh_token = self.get_opt(MicrosoftModule.OPT_AUTH_TOKEN)
        principal = self.get_opt(MicrosoftModule.OPT_AUTH_PRINCIPAL)
        secret = self.get_opt(MicrosoftModule.OPT_AUTH_SECRET)
        tenant = self.get_opt(MicrosoftModule.OPT_AUTH_TENANT)

        if Path(secret).exists() and Path(secret).is_file():
            with open(secret, 'r') as file: secret = file.read()

        return MicrosoftCredential(self.name, principal=principal, secret=secret, tenant=tenant, refresh_token=refresh_token)


    ##### Authentication Helpers #####
    def build_client_assertion(self) -> str:
        '''Build a JWT client asseertation for certificate-based auth'''
        # If called, this means that princpal, secret, and tenant are already ingested
