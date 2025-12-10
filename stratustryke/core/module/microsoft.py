# Author: @vexance
# Purpose: Microsoft365 Modules to interact with M365 or Entra

import time
import jwt

from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

from stratustryke.core.module import StratustrykeModule
from stratustryke.core.credential.microsoft import MicrosoftCredential
from stratustryke.lib import StratustrykeException

MSFT_LOGIN_ENDPOINT = 'login.microsoftonline.com'
MSFT_ARM_ENDPOINT = 'management.microsoft.com'
MSFT_GRAPH_ENDPOINT = 'graph.microsoft.com'

MSFT_DEVICE_CODE_AUTH_URN = 'urn:ietf:params:oauth:grant-type:device_code'
MSFT_CLIENT_ASSERTION_AUTH_URN = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'

AZ_CLI_CLIENT_ID = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
ARM_TOKEN_SCOPE = f'https://{MSFT_ARM_ENDPOINT}/.default'
GRAPH_TOKEN_SCOPE = f'https://{MSFT_GRAPH_ENDPOINT}/.default'
KEYVAULT_TOKEN_SCOPE = 'https://vault.azure.net/.default'
STORAGE_TOKEN_SCOPE = 'https://storage.azure.com/.default'
ACR_TOKEN_SCOPE = 'https://containerregistry.azure.net/.default'
MSFT_COMMON_SCOPES = 'offline_access openid profile'


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

    ##### AuthN helpers for interactive / device code auth #####
    def get_openid_config(self, tenant: str = 'organizations') -> dict | None:
        '''Return OIDC config from the .well-known endpoint'''
        endpoint = f'https://{MSFT_LOGIN_ENDPOINT}/{tenant}/v2.0/.well-known/openid-configuration'

        try:
            res = self.http_request('GET', endpoint)
            res.raise_for_status()
            return res.json()
        
        except Exception as err:
            self.print_failure(f'Unable to get OIDC config at {endpoint}')
            if self.verbose: self.print_error(str(err))
            return None
        
    
    def request_device_code(self, scope: str, tenant: str, client_id: str) -> tuple[str]:
        '''Initiate device code OIDC authentication flow, return (device_code, verification_uri)'''
        endpoint = f'https://{MSFT_LOGIN_ENDPOINT}/{tenant}/oauth2/v2.0/devicecode'
        body = {
            'client_id': client_id,
            'scope': scope
        }

        try:
            res = self.http_request('POST', endpoint, data = body)
            res.raise_for_status()

            content = res.json()
            verify_uri = content.get('verification_uri', None)
            user_code = content.get('user_code', None)
            device_code = content.get('device_code', None)

            if not all([verify_uri, user_code, device_code]):
                raise StratustrykeException(f'Missing verification_uri, user_code, or device_code in response: {res.text}')
            
            self.print_status(f'Authenticate at {verify_uri} with code: {user_code}')
            return device_code #, verify_uri
        
        except Exception as err:
            self.print_failure(f'Failure initiating device code flow at {endpoint}')
            if self.verbose: self.print_error(str(err))
            return None #, None
        

    def poll_device_token(self, code: str, tenant: str, client_id: str) -> str:
        '''Monitor verification uri for a period up to specified timeout for successful/failed AuthN'''
        endpoint = f'https://{MSFT_LOGIN_ENDPOINT}/{tenant}/oauth2/v2.0/token'
        body = {
            'grant_type': MSFT_DEVICE_CODE_AUTH_URN,
            'client_id': client_id,
            'device_code': code
        }

        start = time.time()
        delay = 5 # 5 Seconds between polling requests at the beginning
        timeout = 180 # 3 minute timeout

        while True: # Polling loop
            try:
                res = self.http_request('POST', endpoint, data = body)
                content = res.json()

                # Successdful auth completed
                if res.status_code == 200:
                    refresh_token = content.get('refresh_token', None)
                    if refresh_token == None:
                        raise StratustrykeException(f'Successful auth, but no refresh token found; ensure \'offline_access\' is in token scope: {content}')
                    
                    # access_token = content.get('access_token', None)
                    return refresh_token
                
                
                error = content.get('error', None)

                # Nothing wrong yet; likely waiting for AuthN
                if error in {'authorization_pending', 'slow_down'}:
                    if error == 'slow_down': # Throttling
                        delay += 3
                    polling_time = time.time() - start
                    if polling_time > timeout:
                        raise StratustrykeException(f'Polling exceeded maximum timeout threshold: {content}')
                    
                    time.sleep(delay)

                # Device code is not longer valid
                elif error == 'expired_token':
                    raise StratustrykeException(f'Device code lifespan exceeded while polling for AuthN: {content}')

                # Not a 200 response & unknown / unexpected error
                else: 
                    raise StratustrykeException(f'Unexpected response error {res.status_code}: {content}')
            
            except Exception as err:
                self.print_failure(f'Exception thrown monitoring device code verification URI')
                if self.verbose: self.print_error(str(err))
                return None


    def authenticate_interactive(self, tenant: str = 'organizations', scope: str = GRAPH_TOKEN_SCOPE, client_id: str | None = AZ_CLI_CLIENT_ID) -> str:
        '''Performs interactive authentication using device-code flow in OIDC; return refresh token'''
        code = self.request_device_code(scope, tenant, client_id)
        if not code: return None

        refresh_token = self.poll_device_token(code, tenant, client_id)
        return refresh_token


    ##### AuthN helpers for service princiapl auth #####
    def build_client_assertion(self, tenant: str, client_id: str, key_pem: str) -> str:
        '''Build a JWT client asseertation for service-principal certificate based auth'''
        # If called, this means that princpal, secret, and tenant are already ingested
        token_endpoint = f'https://{MSFT_LOGIN_ENDPOINT}/{tenant}/oauth2/v2.0/token'
        now = datetime.now(timezone.utc)

        # For certificate auth, a payload with this structure is signed with the auth cert pem
        payload = {
            'aud': token_endpoint,
            'iss': client_id,
            'sub': client_id,
            'jti': str(uuid4()), # can be randmon
            'nbf': int(now.timestamp()),
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(minutes=10)).timestamp())
        }

        assertion = jwt.encode(payload, key_pem, algorithm='RS256')
        if isinstance(assertion, bytes):
            assertion = assertion.decode()
        
        return assertion
    

    def is_client_cert_pem(self, text: str) -> bool:
        '''Guess if the string is a client cert or a secret key string'''
        key_strings = {
            'BEGIN PRIVATE KEY',
            'BEGIN RSA PRIVATE KEY',
            'BEGIN EC PRIVATE KEY',
            'BEGIN CERTIFICATE',
            'BEGIN PUBLIC KEY'
        }

        for pattern in key_strings:
            if pattern in text: return True
        
        return False
    

    def load_secret_or_pem(self, path_or_value: str) -> tuple[str, bool]:
        '''Loads a secret value from either a file or direct string.'''
        if Path(path_or_value).exists():
            with open(path_or_value, 'r') as f: content = f.read()
            return content

        # Not a file; treat as raw secret
        return path_or_value


    def service_principal_auth(self, scope: str, tenant: str, client_id: str, secret: str) -> str:
        '''Retrieve an access token for the service principal upon the target scope'''
        endpoint = f'https://{MSFT_LOGIN_ENDPOINT}/{tenant}/oauth2/v2.0/token'
        body = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'scope': scope
        }

        if self.is_client_cert_pem(secret):
            assertion = self.build_client_assertion(tenant, client_id, secret)
            body['client_assertion_type'] = (MSFT_CLIENT_ASSERTION_AUTH_URN)
            body['client_assertion'] = assertion

        else: # Client secret auth
            body['client_secret'] = secret
        
        try:
            res = self.http_request('POST', endpoint, data = body)
            res.raise_for_status()
            content = res.json()

            access_token = content.get('access_token', None)
            if not access_token:
                raise StratustrykeException(f'Authentication succeeded, but no access_token in response: {res.text}')
            
            return access_token
        
        except Exception as err:
            self.print_failure(f'Authentication failed in service principal auth flow')
            if self.verbose: self.print_error(str(err))
            return None


    # def access_token(self, scope: str) -> str: