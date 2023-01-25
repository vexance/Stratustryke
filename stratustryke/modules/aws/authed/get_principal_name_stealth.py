
from stratustryke.core.module import AWSModule
from stratustryke.core.credential import AWSCredential

class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Details': 'Performs an SNS:Publish API call to an arbitrary SNS topic within a valid AWS account using the supplid credentials. The error message returned from a failed call will include the ARN of the callee (entity associated with the supplied credentials).',
            'Description': 'Retrieve the ARN associated with supplied access keys without logging to CloudTrail',
            'References': ['https://hackingthe.cloud/aws/enumeration/whoami/']
        }
        self._options.add_string('ACCOUNT_ID', 'A valid 12-digit AWS account id', True, regex='^[0-9]{12}$')
        self._options.add_string('SNS_TOPIC', 'SNS topic to perform Publish call to', False, 'sns-topic-stratustryke')
        self._options.add_string('SNS_MESSAGE', 'Message to publish to the SNS topic', False, 'sns-message-stratustryke')

    @property
    def search_name(self):
        return f'aws/authed/{self.name}'

    def run(self):
        access_key = self.get_opt('AUTH_ACCESS_KEY_ID')
        secret_key = self.get_opt('AUTH_SECRET_KEY')
        token = self.get_opt('AUTH_SESSION_TOKEN')
        region = self.get_opt('AWS_REGION')

        acc_id = self.get_opt('ACCOUNT_ID')
        topic = self.get_opt('SNS_TOPIC')
        message = self.get_opt('SNS_MESSAGE')

        topic_arn = f'arn:aws:sns:{region}:{acc_id}:{topic}'
        cred = AWSCredential('', access_key=access_key, secret_key=secret_key, session_token=token)

        try:
            session = cred.session()
            client = session.client('sns')

            self.framework.print_status('Attempting SNS:Publish call...')
            res = client.publish(TopicArn=topic_arn, Message=message)
            
            self.framework.print_failure('SNS:Publish successful - unable to identify principle')
            success = False
        except Exception as err:
            # We actually want this to throw a AuthorizationErrorException
            msg = f'{err}'
            if msg.startswith('An error occurred (AuthorizationError) when calling the Publish operation:'):
                self.framework.print_status('Received expected AuthorizationErrorException')
                split = msg.split(' ') # split on whitespace - principle type & ARN should be indexes 9 & 10
                if len(split) > 10:
                    self.framework.print_success(f'Found principle - {split[9]} {split[10]}')
                    return True
                else:
                    self.framework.print_failure('Something went wrong; unexpected response length...')
            else:
                self.framework.print_failure('Unable to identify principle via SNS:Publish')
                self.framework.print_error(f'{err}')
            success = False

        return success

