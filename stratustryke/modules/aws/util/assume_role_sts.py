from stratustryke.core.module import AWSModule
from stratustryke.core.credential import AWSCredential
from stratustryke.core.lib import StratustrykeException

class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Create new AWS credstore credential via sts:AssumeRole call',
            'Details': 'Performs an sts:AssumeRole call with the supplied options. If successful, imports the credentials into the stratustryke credstore',
            'References': ['']
        }

        self._options.add_string('ALIAS', 'Name of alias to import the credential as', True)
        self._options.add_string('WORKSPACE', 'Workspace to import the credential to', True, self.framework._config.get_val('WORKSPACE'))
        self._options.add_string('ROLE_ARN', 'Target ARN of role to assume', True, regex='^arn:aws:iam::[0-9]{12}:role/.*$')
        self._options.add_string('EXTERNAL_ID', 'External Id, if necessary, to use in the call', False, sensitive=True) # can sometimes be sensitive, so we'll play it safe
        self._options.add_integer('DURATION', 'Time (in minutes [15 - ]) for credentials to be valid for', True, 60)
        self._options.add_string('SESSION_NAME', 'Name to designate for the assumed role session', True, 'stratustryke')

    @property
    def search_name(self):
        return f'aws/util/{self.name}'

    def run(self):
        cred = self.get_cred()
        alias = self.get_opt('ALIAS')
        workspace = self.get_opt('WORKSPACE')
        arn = self.get_opt('ROLE_ARN')
        ext_id = self.get_opt('EXTERNAL_ID')
        duration = self.get_opt('DURATION') # * 60 # API requires duration in seconds
        session_name = self.get_opt('SESSION_NAME')
        region = self.get_opt('AWS_REGION')


        try:
            assumed_role_cred = cred.assume_role(arn, ext_id=ext_id, duration=duration, region=region,
                                                 session_name=session_name, workspace=workspace, alias=alias)
            
            self.framework.credentials.store_credential(assumed_role_cred)
            return True

        except Exception as err:
            self.framework.print_failure(f'{err}')
            return False