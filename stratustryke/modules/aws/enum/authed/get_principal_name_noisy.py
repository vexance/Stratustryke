
from stratustryke.core.module import AWSModule

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
        return f'aws/enum/authed/{self.name}'

    def run(self):
        cred = self.get_cred()
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

