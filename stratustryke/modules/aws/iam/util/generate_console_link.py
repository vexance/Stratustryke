
from stratustryke.core.module.aws import AWSModule
from stratustryke.core.credential.aws import AWSCredential
from stratustryke.core.lib import StratustrykeException
import requests
import json
from urllib.parse import quote_plus

class Module(AWSModule):

    OPT_DURATION = 'DURATION'
    OPT_SESSION_NAME = 'SESSION_NAME'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Use sts:CreateFederationToken or temporary credentials to generate an AWS console sign-in link',
            'Details': 'Uses temporary AWS credentials to generate a signin link to the AWS console, allowing use of the console to leverage credentialed access. Temporary credentials (either from sts:AssumeRole or sts:GetFederationToken) MUST be used. If long term credentials (i.e., AKIA...) are set in the options, this module will attempt to use sts:GetFederationToken to retrieve temporary creds. Otherwise, the temporary credentials designated in the module options will be used.',
            'References': [
                'https://hackingthe.cloud/aws/general-knowledge/create_a_console_session_from_iam_credentials/',
                'https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_enable-console-custom-url.html',
                'https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sts.html#STS.Client.get_federation_token'
            ]
        }

        self._options.add_integer(Module.OPT_DURATION, 'Duration in minutes for the console session to be valid for', True, 60)
        self._options.add_string(Module.OPT_SESSION_NAME, 'Name for federated user session if using long-term credentials', False, 'stratustryke', '^[a-zA-Z_=,.@-]*$')


    @property
    def search_name(self):
        return f'aws/iam/util/{self.name}'


    def run(self):
        cred = self.get_cred()
        duration = self.get_opt(Module.OPT_DURATION) * 60 # duration is sent in seconds to the APIs
        policy = str({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowAll",
                    "Effect": "Allow",
                    "Action": "*:*",
                    "Resource": "*"
                }
            ]
        }).replace("'", '"')
        auth_key = self.get_opt('AUTH_ACCESS_KEY_ID')

        federated_credential = False
        session = cred.session()

        if auth_key.startswith('AKIA'): # long-term creds; use sts:GetFederationToken for temp credentials
            if duration > 2160 or duration < 15:
                self.framework.print_failure('sts:GetFederationToken requires duration to be within 15 - 2160 minutes (36 hours)')
                return
            
            session_name = self.get_opt(Module.OPT_SESSION_NAME)

            try:
                self.framework.print_status('Performing sts:GetFederationToken request for temporary credentials')
                client = session.client('sts')
                res = client.get_federation_token(Name=session_name, Policy=policy, DurationSeconds=duration)

                creds = res.get('Credentials', None)
                fed_arn = res.get('FederatedUser', {}).get('Arn', False)
                if (creds == None) or (fed_arn == False):
                    raise StratustrykeException('No credentials within sts:GetFederationToken response')

                fed_key = creds.get('AccessKeyId', False)
                fed_secret = creds.get('SecretAccessKey', False)
                fed_token = creds.get('SessionToken', False)

                if all([fed_key, fed_secret, fed_token]):
                    self.framework.print_status(f'Retrieved federation token for: {fed_arn}')
                    workspace = self.framework._config.get_val('WORKSPACE')
                    federated_credential = AWSCredential(self.name, workspace, default_region=cred._default_region, access_key=fed_key, secret_key=fed_secret, session_token=fed_token)

            except Exception as err:
                self.framework.print_failure('Unable to retrieve temporary credentials with sts:GetFederationToken')
                self.framework._logger.error('Unable to retrieve temporary credentials with sts:GetFederationToken')
                return
        else:
            self.framework.print_status('Temporary credentials detected, skipping sts:GetFederationToken request')

        # Build JSON session string with creds
        if federated_credential:
            url_key = federated_credential._access_key_id
            url_secret = federated_credential._secret_key
            url_token = federated_credential._session_token

        else:
            url_key = auth_key
            url_secret = self.get_opt('AUTH_SECRET_KEY')
            url_token = self.get_opt('AUTH_SESSION_TOKEN')

        if not all([url_key, url_secret, url_token]):
            self.framework.print_failure('Unable to build JSON session string with supplied credentials')
            return
        
        session_string = str({
            'sessionId': url_key,
            'sessionKey': url_secret,
            'sessionToken': url_token
        }).replace("'", '"')
        query_string = quote_plus(session_string)

        if federated_credential:
            federation_endpoint = f'https://signin.aws.amazon.com/federation?Action=getSigninToken&Session={query_string}'
        else:
            federation_endpoint = f'https://signin.aws.amazon.com/federation?Action=getSigninToken&SessionDuration={duration}&Session={query_string}'

        self.framework.print_status('Requesting signin token from federation endpoint')
        try:
            federation_response = requests.get(federation_endpoint)
            federation_token = json.loads(federation_response.text).get('SigninToken', None)
            
            if federation_token == None:
                raise StratustrykeException('Signin token not received from request to federation endpoint')

            self.framework.print_status('Received token from signin.aws.amazon.com/federation')
            self.framework.print_success(f'https://signin.aws.amazon.com/federation?Action=login&Issuer=stratustryke&Destination=https%3A%2F%2Fconsole.aws.amazon.com%2F&SigninToken={federation_token}')

        except Exception as err:
            self.framework.print_failure(f'{err}')
            self.framework._logger.error(f'{err}')
            return



