
from stratustryke.core.module import AWSModule
from stratustryke.core.credential import AWSCredential

class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Performs STS:GetCallerIdentity call to retrieve the ARN for a set for keys',
            'Details': 'Performs an STS:GetCallerIdentity API call in order to retrieve the ARN associated with a set of access keys. Note that this action is logged to CloudTrail and may trigger detection mechanisms.',
            'References': ['']
        }

    @property
    def search_name(self):
        return f'aws/authed/{self.name}'

    def run(self):
        access_key = self.get_opt('AUTH_ACCESS_KEY_ID')
        secret_key = self.get_opt('AUTH_SECRET_KEY')
        token = self.get_opt('AUTH_SESSION_TOKEN')

        cred = AWSCredential('', access_key=access_key, secret_key=secret_key, session_token=token)

        try:
            session = cred.session()
            client = session.client('sts')
            res = client.get_caller_identity()

            arn = res.get('Arn', res.get('UserId', None))
            if arn == None:
                self.framework.print_failure('Unable to perform STS:GetCallerIdentity')
            self.framework.print_success(f'Found principle - {arn}')
            return True

        except Exception as err:
            self.framework.print_error(f'{err}')
            return False

