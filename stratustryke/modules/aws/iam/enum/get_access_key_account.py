
from stratustryke.core.module.aws import AWSModule

class Module(AWSModule):

    OPT_TARGET_KEY = 'TARGET_KEY'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Details': 'Performs sts get-access-key info call to retrieve the AWS account id associated with an access key id. This will only be logged to the account calling the STS API (not the target account being enumerated).',
            'Description': 'Perform sts get-access-key info call against target aws access key id',
            'References': [
                'https://hackingthe.cloud/aws/enumeration/get-account-id-from-keys/'
            ]
        }

        self._options.add_string(Module.OPT_TARGET_KEY, 'Target AWS access key id to enumerate account id for (f/p)', True)


    @property
    def search_name(self):
        return f'aws/iam/enum/{self.name}'


    def run(self):
        target_keys = self.get_opt_multiline(Module.OPT_TARGET_KEY)

        session = self.get_cred().session() # Might need to code region in? Testing empty for now...
        client = session.client('sts')

        self.print_status(f'Resolving access key identifiers via sts:GetAccessKeyInfo call(s)...')
        
        for key_id in target_keys:
            try:
                res = client.get_access_key_info(AccessKeyId=key_id)
                target_account = res.get('Account', None)
                self.print_success(f'{key_id} is associated with account {target_account}')

            except Exception as err:
                self.print_failure(f'Could not identify account for key id {key_id}')
                if self.verbose: self.print_error(f'{err}')
                continue

        return None
