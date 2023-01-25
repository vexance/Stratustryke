
from stratustryke.core.credential import AWSCredential
from stratustryke.core.module import AWSModule
from stratustryke.settings import AWS_DEFAULT_REGION

class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Import AWS programmatic credentials into the credstore',
            'Details': 'Import AWS programmatic credentials into the credstore',
            'References': ['']
        }
        self._options.add_string('ALIAS', 'Alias name for the credential', True)
        self._options.add_string('WORKSPACE', 'Workspace to associate with the credential', True, default=self.framework._config.get_val('WORKSPACE'))
        self._options.add_string('ACCOUNT_ID', '12 digit AWS account id', False, sensitive=True, regex='^[0-9]{12}$')
        self._options.add_string('ARN', 'Amazon resource name for the credential', False, sensitive=True)
        self._options.add_string('DEFAULT_REGION', 'Default AWS region for the credential\'s sessions', False, AWS_DEFAULT_REGION)


    @property
    def search_name(self):
        return f'aws/util/{self.name}'

    def run(self):
        access_key = self.get_opt('AUTH_ACCESS_KEY_ID')
        secret_key = self.get_opt('AUTH_SECRET_KEY')
        session_token = self.get_opt('AUTH_SESSION_TOKEN')
        alias = self.get_opt('ALIAS')
        acc_id = self.get_opt('ACCOUNT_ID')
        arn = self.get_opt('ARN')
        region = self.get_opt('DEFAULT_REGION')
        workspace = self.get_opt('WORKSPACE')

        cred = AWSCredential(alias, workspace, False, acc_id, access_key, access_key, secret_key, session_token, region, arn)
        self.framework.credentials.store_credential(cred)

        return True
