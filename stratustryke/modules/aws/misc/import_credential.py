

from stratustryke.core.module.aws import AWSModule
from stratustryke.core.credential.aws import AWSCredential
from stratustryke.settings import AWS_DEFAULT_REGION

class Module(AWSModule):

    OPT_ALIAS_NAME = 'ALIAS'
    OPT_WORKSPACE = 'WORKSPACE'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Import AWS programmatic credentials into the credstore',
            'Details': 'Import AWS programmatic credentials into the credstore',
            'References': ['']
        }


        self._options.add_string(Module.OPT_ALIAS_NAME, 'Alias name for the credential', True)
        self._options.add_string(Module.OPT_WORKSPACE, 'Workspace to associate with the credential', True, default=self.framework._config.get_val(self.framework.CONF_WORKSPACE))
        self._options.set_opt(Module.OPT_AWS_REGION, AWS_DEFAULT_REGION)


    @property
    def search_name(self):
        return f'aws/misc/{self.name}'


    def run(self):
        access_key = self.get_opt(Module.OPT_ACCESS_KEY)
        secret_key = self.get_opt(Module.OPT_SECRET_KEY)
        session_token = self.get_opt(Module.OPT_SESSION_TOKEN)
        alias = self.get_opt(Module.OPT_ALIAS_NAME)
        region = self.get_opt(Module.OPT_AWS_REGION)
        workspace = self.get_opt(Module.OPT_WORKSPACE)

        if region == None or region == '':
            region = AWS_DEFAULT_REGION

        # First None val passed is for account id (to be deprecated in place of a property derived from GetCallerIdentity)
        # Second None val is for ARN (also to be deprecated and replaced with property derived from GetCallerIdentity)
        cred = AWSCredential(alias, workspace, False, None, access_key, access_key, secret_key, session_token, region, None)
        self.framework.credentials.store_credential(cred)

        return True
