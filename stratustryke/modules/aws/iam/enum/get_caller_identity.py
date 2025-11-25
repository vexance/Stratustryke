
from stratustryke.core.module.aws import AWSModule

class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Performs sts:GetCallerIdentity call to retrieve the ARN for a set for keys',
            'Details': 'Performs an sts:GetCallerIdentity API call in order to retrieve the ARN associated with a set of access keys. Note that this action is logged to CloudTrail and may trigger detection mechanisms.',
            'References': ['']
        }


    @property
    def search_name(self):
        return f'aws/iam/enum/{self.name}'


    def run(self):
        region = self.get_regions(multi_support=False)[0]
        try:
            client = self.get_cred().session(region).client('sts')
            res = client.get_caller_identity()

            arn = res.get('Arn', res.get('UserId', None))
            if arn == None:
                self.print_failure('Unable to perform sts:GetCallerIdentity with supplied credentials')
            
            self.print_success(arn)

        except Exception as err:
            self.print_failure('Unable to perform sts:GetCallerIdentity with supplied credentials')
            if self.verbose: self.print_error(str(err))

        return None
