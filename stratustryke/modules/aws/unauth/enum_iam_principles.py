from stratustryke.core.module import AWSModule
from stratustryke.core.credential import AWSCredential
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
        return f'aws/unauth/{self.name}'


    def get_policy(self, type: str, name: str) -> str:
        account = self.get_opt('ACCOUNT_ID')
        bucket = self.get_opt('S3_BUCKET')
        return str({
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Sid': 'StratustrykeEnumIAMPrinciples',
                    'Effect': 'Deny',
                    'Principal': {
                        'AWS': f'arn:aws:iam::{account}:{type}/{name}'
                    },
                    'Action': 's3:ListBucket',
                    'Resource': f'arn:aws:s3:::{bucket}'
                }
            ]
        }).replace("'", '"')


    def run(self):
        cred = self.get_cred()
        session = cred.session()

        bucket = self.get_opt('S3_BUCKET')
        verbose = self.get_opt('VERBOSE')
        account = self.get_opt('ACCOUNT_ID')

        # Make sure the designated S3 bucket exists
        self.framework.print_status('Verifying s3 bucket exists')
        try:
            res = requests.get(f'http://{bucket}.s3.amazonaws.com')
            if '<Code>NoSuchBucket</Code>' in res.text:
                raise StratustrykeException(f'Could not verify bucket exists: s3://{bucket}')

        except Exception as err:
            self.framework.print_failure(f'{err}')
            return

        # Attempt to load wordlist
        path = Path(self.get_opt('WORDLIST'))
        if not (path.exists() and path.is_file()):
            self.framework.print_failure(f'Unable to load wordlist contents: {path.absolute()}')
            return

        with open(path, 'r') as file:
            wordlist = [line.strip() for line in file.readlines()]
        self.framework.print_status(f'Loaded {len(wordlist)} entries from {path}')        
        
        # Now enumerate the IAM principles
        self.framework.print_status(f'Enumerating IAM principles in account: {account}')
        for principle in wordlist:
            user_policy = self.get_policy('user', principle)
            role_policy = self.get_policy('role', principle)

            client = session.client('s3')

            try:
                client.put_bucket_policy(Bucket=bucket, Policy=user_policy)   
                self.framework.print_success(f'arn:aws:iam::{account}:user/{principle}')
            except Exception:
                if verbose:
                    self.framework.print_failure(f'arn:aws:iam::{account}:user/{principle}')
                self.framework._logger.info(f'Principle does not exist: arn:aws:iam::{account}:user/{principle}')

            try:
                client.put_bucket_policy(Bucket=bucket, Policy=role_policy)
                self.framework.print_success(f'arn:aws:iam::{account}:role/{principle}')
            except Exception:
                if verbose:
                    self.framework.print_failure(f'arn:aws:iam::{account}:role/{principle}')
                self.framework._logger.info(f'Principle does not exist: arn:aws:iam::{account}:user/{principle}')

        