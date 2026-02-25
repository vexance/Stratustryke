
from stratustryke.core.credential import APICredential, GenericCredential
from stratustryke.core.module import StratustrykeModule

class Module(StratustrykeModule):

    OPT_ALIAS = 'ALIAS'
    OPT_WORKSPACE = 'WORKSPACE'
    OPT_CREDENTIAL_TYPE = 'CREDENTIAL_TYPE'
    OPT_USERNAME = 'USERNAME'
    OPT_PASSWORD = 'PASSWORD'
    OPT_AUTH_TYPE = 'AUTH_TYPE'
    OPT_API_ENDPOINT = 'API_ENDPOINT'
    OPT_API_SECRET = 'API_SECRET'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Import a generic user/pass or api credential into the credstore',
            'Details': 'Import a generic user/pass or api credential into the credstore',
            'References': ['']
        }
        self._options.add_string(Module.OPT_ALIAS, 'Alias name for the credential', True)
        self._options.add_string(Module.OPT_WORKSPACE, 'Workspace to associate with the credential', True, default=self.framework._config.get_val(self.framework.CONF_WORKSPACE))
        self._options.add_string(Module.OPT_CREDENTIAL_TYPE, 'Type of credentials to import [API, GENERIC]', True, regex='^(API|GENERIC)$')
        self._options.add_string(Module.OPT_USERNAME, 'For generic creds, username associated with credential', False)
        self._options.add_string(Module.OPT_PASSWORD, 'For generic creds, the user\'s password', False, sensitive=True)
        self._options.add_string(Module.OPT_AUTH_TYPE, 'For API creds, the authentication type [HEADER, KEY]', False, regex='^(HEADER|KEY($')
        self._options.add_string(Module.OPT_API_ENDPOINT, 'For API creds, the associated URL / endpoint', False)
        self._options.add_string(Module.OPT_API_SECRET, 'For API creds, the api key or request header', False, sensitive=True)

    @property
    def search_name(self) -> str:
        return f'generic/util/{self.name}'

    def run(self) -> bool:

        alias = self.get_opt(Module.OPT_ALIAS)
        workspace = self.get_opt(Module.OPT_WORKSPACE)
        cred_type = self.get_opt(Module.OPT_CREDENTIAL_TYPE)

        if cred_type == 'GENERIC':
            username = self.get_opt(Module.OPT_USERNAME)
            pswd = self.get_opt(Module.OPT_PASSWORD)

            cred = GenericCredential(alias, workspace, user=username, pswd=pswd)
            self.framework.credentials.store_credential(cred)
        elif cred_type == 'API':
            auth_type = self.get_opt(Module.OPT_AUTH_TYPE)
            url = self.get_opt(Module.OPT_API_ENDPOINT)
            secret = self.get_opt(Module.OPT_API_SECRET)

            cred = APICredential(alias, workspace, auth_type=auth_type, secret=secret, endpoint=url)
            self.framework.credentials.store_credential(cred)
        else:
            self.print_failure(f'Invalid credential type: {cred_type}')
            return False

        self.print_status(f'Imported credential with alias: {alias}')
        return True

        return True