
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
        self._options.set_opt('AWS_REGION', AWS_DEFAULT_REGION)


    @property
    def search_name(self):
        return f'aws/util/{self.name}'

    def run(self):
        access_key = self.get_opt('AUTH_ACCESS_KEY_ID')
        secret_key = self.get_opt('AUTH_SECRET_KEY')
        session_token = self.get_opt('AUTH_SESSION_TOKEN')
        alias = self.get_opt('ALIAS')
        region = self.get_opt('AWS_REGION')
        workspace = self.get_opt('WORKSPACE')

        if region == None or region == '':
            region = AWS_DEFAULT_REGION

        # First None val passed is for account id (to be deprecated in place of a property derived from GetCallerIdentity)
        # Second None val is for ARN (also to be deprecated and replaced with property derived from GetCallerIdentity)
        cred = AWSCredential(alias, workspace, False, None, access_key, access_key, secret_key, session_token, region, None)
        self.framework.credentials.store_credential(cred)

        return True
