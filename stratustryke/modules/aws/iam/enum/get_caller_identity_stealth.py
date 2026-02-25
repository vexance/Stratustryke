
from stratustryke.core.module.aws import AWSModule

class Module(AWSModule):

    OPT_ACCOUNT_ID = 'ACCOUNT_ID'
    OPT_SNS_TOPIC = 'SNS_TOPIC'


    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Details': 'Performs an sns:Publish API call to an arbitrary SNS topic within a valid AWS account using the supplid credentials. The error message returned from a failed call will include the ARN of the callee (entity associated with the supplied credentials).',
            'Description': 'Retrieve ARN for the calling principal w/o logging to CloudTrail',
            'References': ['https://hackingthe.cloud/aws/enumeration/whoami/']
        }
        
        self._options.add_string(Module.OPT_ACCOUNT_ID, 'A valid 12-digit AWS account id', True, regex='^[0-9]{12}$')
        self._options.add_string(Module.OPT_ACCOUNT_ID, 'SNS topic name to perform Publish call to', False, 'sns-topic-stratustryke')


    @property
    def search_name(self):
        return f'aws/iam/enum/{self.name}'


    def run(self):
        region = self.get_regions(multi_support=False)[0]

        acc_id = self.get_opt(Module.OPT_ACCOUNT_ID)
        topic = self.get_opt(Module.OPT_ACCOUNT_ID)

        topic_arn = f'arn:aws:sns:{region}:{acc_id}:{topic}'

        try:
            client = self.get_cred().session(region).client('sns')

            self.print_status('Attempting sns:Publish call...')
            res = client.publish(TopicArn=topic_arn, Message='sns-message-stratustryke')
            
            self.print_failure('sns:Publish succeeded unexpectedly - unable to identify principle')
            success = False

        except Exception as err:
            # We actually want this to throw a AuthorizationErrorException
            msg = f'{err}'
            if msg.startswith('An error occurred (AuthorizationError) when calling the Publish operation:'):
                self.print_status('Received expected AuthorizationErrorException')
                split = msg.split(' ') # split on whitespace - principle type & ARN should be indexes 9 & 10
                if len(split) > 10:
                    self.print_success(f'Found principle - {split[9]} {split[10]}')
                    return True
                else:
                    self.print_failure('Something went wrong; unexpected response length...')
            else:
                self.print_failure('Unable to identify principle via SNS:Publish')
                self.print_error(f'{err}')
            success = False

        return success

