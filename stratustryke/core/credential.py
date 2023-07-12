import boto3
from ast import literal_eval
from stratustryke.core.lib import StratustrykeException
from stratustryke.settings import AWS_DEFAULT_REGION
from stratustryke.settings import DEFAULT_WORKSPACE
from re import match as regex_match
from requests_auth_aws_sigv4 import AWSSigV4


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
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verfied: bool = False, user: str = None, pswd: str = None, from_dict: dict = None):
        if from_dict != None:
            return super().__init__(alias, from_dict=from_dict)
        else:
            super().__init__(alias, workspace, verfied)
            self._username = user
            self._password = pswd


    def __str__(self) -> str:
        tmp = super().__str__()
        builder = literal_eval(tmp)
        builder['_username'] = self._username
        builder['_password'] = self._password
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
        session = self.get_boto_session()
        client = session.client('sts')
        try:
            res = client.get_caller_identity()
            self._account_id = res.Account
            self._aws_identity = res.Arn
            self._user_id = res.UserId
            self._verified = True
        except Exception as err:
            raise StratustrykeException(f'Failed to perform get-caller-identity call for \'{self._access_key_id}\'')

        return True
    

    def assume_role(self, role: str, ext_id: str = '', policy: str = None, duration: int = 15,
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
        if not regex_match('^arn:aws:iam::[0-9]{12}:role/.*$', role):
            role = f'arn:aws:iam::{self._account_id}:role/{role}'

        # Check / fix args
        if region == None: region = self._default_region # use current default if not supplied
        duration = duration * 60 # Cast minutes to seconds
        #if ext_id == '': ext_id = None
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

            if not all([access_key, secret_key, token]):
                raise StratustrykeException(f'Did not retrieve all of aws_acess_key_id, aws_secret_access_key, aws_session_token')

            return AWSCredential(alias, access_key=access_key, secret_key=secret_key, session_token=token,
                                 default_region=region, workspace=workspace)
        
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
        

        
class AzureCredential(CloudCredential):
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verified: bool = False, 
        cred_id: str = None, acc_id: str = None, from_dict: dict = None):

        if from_dict != None:
            return super.__init__(alias, from_dict=from_dict)

        super().__init__(alias, workspace, verified, cred_id, acc_id)

    def __str__(self) -> str:
        return super().__str__()


class GCPCredential(CloudCredential):
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verified: bool = False, 
        cred_id: str = None, acc_id: str = None, from_dict: dict = None):

        if from_dict != None:
            return super.__init__(alias, from_dict=from_dict)

        super().__init__(alias, workspace, verified, cred_id, acc_id)

    def __str__(self) -> str:
        return super().__str__()