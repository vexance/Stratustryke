from stratustryke.core.module import AWSModule
from stratustryke.core.lib import StratustrykeException


class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)

        self._info = {
            'Authors': ['@vexance'],
            'Details': 'Inspects Cloudtrail logs for records of successful API calls, determining which principals have potential permissions within the account',
            'Description': 'Identify successful API calls made by principals',
            'References': ['']
        }

        self._options.add_integer('TIMEDELTA_DAYS')
        self._options.add_integer('PRINCIPAL')


    @property
    def search_name(self):
        return f'aws/enum/authed/{self.name}'
    

    def fetch_records(self) -> list:
        '''Paginate through CloudTrail events'''


    def run(self):

        return None