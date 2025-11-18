import boto3
from ast import literal_eval
from stratustryke.core.lib import StratustrykeException
from stratustryke.settings import AWS_DEFAULT_REGION
from stratustryke.settings import DEFAULT_WORKSPACE
from re import match as regex_match
from requests_auth_aws_sigv4 import AWSSigV4
from re import match as regex_match
import azure.identity


AWS_ROLE_ARN_REGEX = '^arn:aws:iam::[0-9]{12}:role/.*$'
AZ_CLI_CLIENT_ID = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
AZ_MGMT_TOKEN_SCOPE = 'https://management.azure.com/.default'
M365_GRAPH_TOKEN_SCOPE = 'https://graph.microsoft.com/.default'
UUID_LOWERCASE_REGEX = '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'


class Credential:
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verfied: bool = False, from_dict: str = None):
        if from_dict != None:
            from_dict = literal_eval(from_dict)
            for key in from_dict.keys():
                attr = str(key)
                self.__setattr__(attr, from_dict.get(key))
            return
        else:
            self._alias = alias
            self._workspace = workspace
            self._verified = verfied


    def __str__(self) -> str:
        builder = {}
        builder['_alias'] = self._alias
        builder['_verified'] = self._verified
        builder['_workspace'] = self._workspace
        return str(builder)

    
    def to_string(self) -> str:
        return self.__str__()


class GenericCredential(Credential):
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verfied: bool = False, secret_name: str = None, secret_value: str = None, from_dict: dict = None):
        if from_dict != None:
            return super().__init__(alias, from_dict=from_dict)
        else:
            super().__init__(alias, workspace, verfied)
            self._secretname = secret_name
            self._secretvalue = secret_value


    def __str__(self) -> str:
        tmp = super().__str__()
        builder = literal_eval(tmp)
        builder['_secretname'] = self._secretname
        builder['_secretvalue'] = self._secretvalue
        return str(builder)


class APICredential(Credential):
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verfied: bool = False, auth_type: str = None, secret: str = None, endpoint: str = None, from_dict: dict = None):
        if from_dict != None:
            return super().__init__(alias, from_dict=from_dict)
        else:
            super().__init__(alias, workspace, verfied)
            self._auth_type = auth_type # Key, Authorization: Bearer, etc
            self._secret = secret
            self._endpoint = endpoint

    def __str__(self) -> str:
        tmp = super().__str__()
        builder = literal_eval(tmp)
        builder['_auth_type'] = self._auth_type
        builder['_secret'] = self._secret
        builder['_endpoint'] = self._endpoint
        return str(builder)


class CloudCredential(Credential):
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verfied: bool = False, acc_id: str = None, cred_id: str = None, from_dict: dict = None):
        if from_dict != None:
            return super().__init__(alias, from_dict=from_dict)
        else:
            super().__init__(alias, workspace, verfied)
            self._account_id = acc_id
            self._cred_id = cred_id

    def __str__(self) -> str:
        tmp = super().__str__()
        builder = literal_eval(tmp)
        builder['_account_id'] = self._account_id
        builder['_cred_id'] = self._cred_id
        return str(builder)


class AWSCredential(CloudCredential):
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verfied: bool = False, acc_id: str = None, 
        cred_id: str = None, access_key: str = None, secret_key: str = None, session_token: str = None, 
        default_region: str = AWS_DEFAULT_REGION, arn: str = None, from_dict: dict = None):
        
        if from_dict != None:
            return super().__init__(alias,from_dict=from_dict)
        else:
            super().__init__(alias, workspace, verfied, acc_id, cred_id)
            self._access_key_id = access_key
            self._secret_key = secret_key
            self._session_token = session_token
            self._default_region = default_region
            self._arn = arn
            self._session = None


    def __str__(self) -> str:
        tmp = super().__str__()
        builder = literal_eval(tmp)
        builder['_access_key_id'] = self._access_key_id
        builder['_secret_key'] = self._secret_key
        builder['_session_token'] = self._session_token
        builder['_default_region'] = self._default_region
        builder['_arn'] = self._arn
        builder['_session'] = None # can't really copy a boto3.Session object as a string
        return str(builder)


    @property
    def account_id(self) -> str:
        if self._account_id != None: return self._account_id
        else: # haven't gotten account_id yet
            success = self.verify()
            if success: return self._account_id
            else: return None


    @property
    def arn(self) -> str:
        if self._arn != None: return self._arn
        else:
            success = self.verify()
            if success: return self._arn
            else: return None


    @property
    def user_id(self) -> str:
        if self._user_id != None: return self._user_id
        else:
            success = self.verify()
            if success: return self._user_id
            else: return None


    def session(self, region = None) -> boto3.Session:
        '''Returns a botocore session for the creds'''
        session_region = region if (region != None) else self._default_region
        # Create botocore session with either specified or default region
        try:
            self._session = boto3.Session(self._access_key_id, self._secret_key, self._session_token, session_region)
        except Exception as err:
            self._session = None
            raise StratustrykeException(f'Unable to get Botocore session for AWS credential \'{self._access_key_id}\'\n{err}')

        return self._session


    def verify(self) -> bool:
        '''Performs an STS get-caller-identity call in order to determine the access_key_id, secret_key, and session_token are valid'''
        session = self.session() # Might need to hardcode region in case __DEFAULT__ is defaulted to
        try:
            client = session.client('sts')
            res = client.get_caller_identity()

            self._account_id = res['Account']
            self._arn = res['Arn']
            self._user_id = res['UserId']
            self._verified = True
        except Exception as err:
            raise StratustrykeException(f'Failed to perform get-caller-identity call for \'{self._access_key_id}\' {err}')

        return True
    

    def assume_role(self, role: str, ext_id: str = 'stratustryke', policy: str = None, duration: int = 15,
                    region: str = None, session_name: str = 'stratustryke', workspace: str = DEFAULT_WORKSPACE,
                    alias: str = 'AssumedRoleCred') -> CloudCredential:
        '''Performs an STS assume-role call, tuple<bool, CloudCredential> with success status, assumed role credentials.
        :param role: Can be either just the role name (will use current account id to build the target role ARN), or a full role ARN
        :param ext_id: String external id if necessary to assume the role
        :param policy: String (or JSON) policy to use as inline session policy to restrict permissions
        :param duration: Number of minutes to assume the role for [default: 15]
        :param region: Default AWS region for the new AWSCredential object
        :param session_name: String name for the assumed role session [default: stratustryke]
        :return: AWSCredential object for the assumed role creds
        '''

        # If an arn isn't supplied, attempt to use the input as a name of a role within the caller's account
        if not regex_match(AWS_ROLE_ARN_REGEX, role):
            role = f'arn:aws:iam::{self._account_id}:role/{role}'

        # Check / fix args
        if region == None: region = self._default_region # use current default if not supplied
        duration = duration * 60 # Cast minutes to seconds

        if isinstance(policy, dict): policy = str(policy).replace('\'', '\"')
        if policy == None: # If policy not supplied, pass one allowing *:*
            policy = '{"Version": "2012-10-17", "Statement": {"Effect": "Allow", "Action": "*", "Resource": "*"} }'

        try: 
            session = self.session()
            client = session.client('sts')
            res = client.assume_role(RoleSessionName=session_name, RoleArn=role, DurationSeconds=duration, ExternalId=ext_id, Policy=policy)

            access_key = res.get('Credentials', {}).get('AccessKeyId', False)
            secret_key = res.get('Credentials', {}).get('SecretAccessKey', False)
            token = res.get('Credentials', {}).get('SessionToken', False)

            arn = res.get('AssumeRoleUser', {}).get('Arn', None)
            acc_id = arn.split(':')[4] if (arn != None) else None

            if not all([access_key, secret_key, token]):
                raise StratustrykeException(f'Did not retrieve all of aws_acess_key_id, aws_secret_access_key, aws_session_token')

            return AWSCredential(alias, access_key=access_key, secret_key=secret_key, session_token=token,
                                 default_region=region, workspace=workspace, arn=arn, acc_id=acc_id)
        
        except Exception as err:
            raise StratustrykeException(f'Exception thrown performing sts:AssumeRole for {role}\n{err}')


    def sigv4(self, service: str, region: str = None) -> AWSSigV4:
        '''Returns and AWSSigV4 object for the credential that can be used to sign HTTP requests'''
        if region == None: region = self._default_region
        return AWSSigV4(
            service,
            region = region, 
            aws_access_key_id = self._access_key_id,
            aws_secret_access_key = self._secret_key,
            aws_session_token = self._session_token
        )


class MicrosoftCredential(CloudCredential):

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
            raise StratustrykeException('Attempting to re-scope existing Microsoft Graph access token')
        
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




class GCPCredential(CloudCredential):
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verified: bool = False, 
        cred_id: str = None, acc_id: str = None, from_dict: dict = None):

        if from_dict != None:
            return super.__init__(alias, from_dict=from_dict)

        super().__init__(alias, workspace, verified, cred_id, acc_id)

    def __str__(self) -> str:
        return super().__str__()

