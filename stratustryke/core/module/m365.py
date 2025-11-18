# Author: @vexance
# Purpose: Microsoft365 Modules to interact with M365 or Entra

from stratustryke.core.module import StratustrykeModule
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


class M365Module(StratustrykeModule):

    OPT_AUTH_TOKEN = 'AUTH_TOKEN'
    OPT_AUTH_PRINCIPAL = 'AUTH_PRINCIPAL'
    OPT_AUTH_SECRET = 'AUTH_SECRET'
    OPT_AUTH_TENANT = 'AUTH_TENANT'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._options.add_string(M365Module.OPT_AUTH_TOKEN, 'Pre-existing access token for Microsoft Graph; overrides other AUTH_* options', False, sensitive=True)
        self._options.add_string(M365Module.OPT_AUTH_PRINCIPAL, 'Entra service principal id, email, or managed identity', False)
        self._options.add_string(M365Module.OPT_AUTH_SECRET, 'Authentication secret (e.g, client secret / password)', False, sensitive=True)
        self._options.add_string(M365Module.OPT_AUTH_TENANT, 'Azure tenant / directory identifer; required if AUTH_TOKEN not set', False, regex='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
        self._cred = None


    @property
    def search_name(self):
        return f'm365/{self.name}'
    

    def get_cred(self,):
        access_token = self.get_opt(M365Module.OPT_AUTH_TOKEN)
        principal = self.get_opt(M365Module.OPT_AUTH_PRINCIPAL)
        secret = self.get_opt(M365Module.OPT_AUTH_SECRET)
        tenant = self.get_opt(M365Module.OPT_AUTH_TENANT)

        return stratustryke.core.credential.MicrosoftCredential(f'{self.name}', principal=principal, secret=secret, tenant=tenant, access_token=access_token)

