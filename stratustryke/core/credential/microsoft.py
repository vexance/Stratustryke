
import azure.identity

from re import match as regex_match
from ast import literal_eval

from stratustryke.core.credential import CloudCredential
from stratustryke.settings import DEFAULT_WORKSPACE
from stratustryke.lib import StratustrykeException
from stratustryke.lib.regex import UUID_LOWERCASE_REGEX


AZ_CLI_CLIENT_ID = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
AZ_MGMT_TOKEN_SCOPE = 'https://management.azure.com/.default'
M365_GRAPH_TOKEN_SCOPE = 'https://graph.microsoft.com/.default'


class MicrosoftCredential(CloudCredential):

    CREDENTIAL_TYPE = 'MSFT'

    # For AzureCredential, the account_id will indicate the subscription id
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verified: bool = False, 
        acc_id: str = None, cred_id: str = None, from_dict: dict = None, principal: str = None, secret: str = None,
        tenant: str = None, interactive: bool = False, access_token: str = None,
        token_scope: str = M365_GRAPH_TOKEN_SCOPE):

        if from_dict != None:
            return super().__init__(alias, from_dict=from_dict)
        else:
            super().__init__(alias, workspace, verified, acc_id, cred_id)
            self._principal = principal
            self._secret = secret
            self._tenant = tenant
            self._access_token = access_token
            self._interactive = interactive
            self._token_scope = token_scope


    def __str__(self) -> str:
        tmp = super().__str__()
        builder = literal_eval(tmp)
        builder['_principal'] = self._principal
        builder['_secret'] = self._secret
        builder['_tenant'] = self._tenant
        builder['_access_token'] = self._access_token
        builder['_interactive'] = self._interactive
        builder['_token_scope'] = self._token_scope
        return str(builder)


    def store_token(self) -> None:
        self._access_token = self.access_token()


    def access_token(self, scope: str = None) -> str:
        '''Retrieve access token for the given scope. NOTE: Cannot overwrite scope if the access token has already been set'''
        
        # Scope is unchanged & access token has already been retrieved
        if (scope == self._token_scope or scope == None) and self._access_token != None:
            return self._access_token
        
        # This might break things but we'll see :|
        elif (scope != self._token_scope) and self._access_token != None:
            # raise StratustrykeException('Cannot re-scope existing Microsoft Graph access token')
            return self._access_token
        
        TOKEN_SCOPE = scope if (scope != None) else self._token_scope
        

        if (self._interactive) or (self._principal == None and self._secret == None):
            try:
                cred = azure.identity.DeviceCodeCredential(client_id=AZ_CLI_CLIENT_ID, tenant_id=self._tenant)
            except Exception as err:
                raise StratustrykeException(f'Error getting interactive browser credentials: {err}')
        
        else:

            if not all([self._tenant, self._principal, self._secret]): raise StratustrykeException('Missing at least one of AUTH_TENANT, AUTH_PRINCIPAL, and AUTH_SECRET')

            try:
                # Likely service principal as this is set as a UUID
                if regex_match(UUID_LOWERCASE_REGEX, self._principal):
                    cred = azure.identity.ClientSecretCredential(tenant_id=self._tenant, client_id=self._principal, client_secret=self._secret)
                else:  # Can't be a service principal; use default client_id for azure CLI
                    cred = azure.identity.UsernamePasswordCredential(tenant_id=self._tenant, username=self._principal, password=self._secret, client_id=AZ_CLI_CLIENT_ID)

            except Exception as err:
                raise StratustrykeException(f'Error during service principal / user auth: {err}')

        access_token = cred.get_token(TOKEN_SCOPE)
        token = str(access_token.token)


        if token == None: raise StratustrykeException('Unable to obtain Microsoft access token')
        
        return token

