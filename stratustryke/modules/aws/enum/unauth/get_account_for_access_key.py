from stratustryke.core.module import AWSModule

class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._options.add_string('ENUM_KEY', 'Target AWS access key id to enumerate account id for', True, regex='(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}')
        self._info = {
            'Authors': ['@vexance'],
            'Details': 'Performs sts get-access-key info call to retrieve the AWS account id associated with an access key id. This will only be logged to the account calling the STS API (not the target account being enumerated).',
            'Description': 'Perform sts get-access-key info call against target aws access key id',
            'References': [
                'https://hackingthe.cloud/aws/enumeration/get-account-id-from-keys/'
            ]
        }

    @property
    def search_name(self):
        return f'aws/enum/unauth/{self.name}'

    def run(self) -> bool:
        enum_key = self.get_opt('ENUM_KEY')

        cred = self.get_cred()

        try:
            session = cred.session()
            client = session.client('sts')
            
            self.framework.print_status(f'Performing sts get-access-key-info call...')
            res = client.get_access_key_info(AccessKeyId=enum_key)
            target_account = res.get('Account')
            success = True
            self.framework.print_success(f'Found Account Id \'{target_account}\'')
        except Exception as err:
            self.framework.print_error(f'{err}')
            success = False

        self.framework.print_line('')
        return success
