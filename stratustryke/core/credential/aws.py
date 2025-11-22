import boto3

from ast import literal_eval
from requests_auth_aws_sigv4 import AWSSigV4
from re import match as regex_match

from stratustryke.core.credential import CloudCredential
from stratustryke.settings import AWS_DEFAULT_REGION, DEFAULT_WORKSPACE
from stratustryke.lib import StratustrykeException
from stratustryke.lib.regex import AWS_ROLE_ARN_REGEX


class AWSCredential(CloudCredential):

    CREDENTIAL_TYPE = 'AWS'

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

