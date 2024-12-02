from stratustryke.core.module import AWSModule
from pathlib import Path
import requests
from stratustryke.core.lib import StratustrykeException

class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Enumerate IAM users & roles in a target AWS account',
            'Details': 'Performs s3:PutBucketPolicy calls while attempting to deny various AWS principles access to an s3 bucket you own. Errors are returned by the API call when an invalid AWS principle is supplied in the request, therefore this call can be used to enumerate valid principles.',
            'References': [
                'https://hackingthe.cloud/aws/enumeration/enum_iam_user_role/'
            ]
        }
        self._options.add_string('S3_BUCKET', 'S3 bucket you control to explicitly deny access to', True)
        self._options.add_string('ACCOUNT_ID', '12-digit id for the target AWS account to enumerate principles', True, regex='^[0-9]{12}$')
        self._options.add_string('WORDLIST', 'Path to wordlist containing names to enumerate', True)
        self._options.add_boolean('VERBOSE', 'When enabled, displays IAM principles attempted which were not valid', True, True)

    
    @property
    def search_name(self):
        return f'aws/exfil/authed/{self.name}'
    
    def run(self):
