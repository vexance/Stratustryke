from stratustryke.core.module import AWSModule
from stratustryke.core.lib import StratustrykeException
from datetime import datetime, timedelta


class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)

        self._info = {
            'Authors': ['@vexance'],
            'Details': 'Inspects Cloudtrail logs and extracts referenced resource ARNs',
            'Description': 'Query events from CloudTrail insights and extract ARNs',
            'References': ['']
        }

        self._options.add_integer('TIMEDELTA_DAYS', 'Time period in days of events to include', True, 90)



    @property
    def search_name(self):
        return f'aws/enum/authed/{self.name}'
    

    def fetch_records(self, read_only: bool) -> list:
        '''Paginate through CloudTrail events'''
        session = self.get_cred().session()
        records = []

        # Determine timeframe limits
        delta = self.get_opt('TIMEDELTA_DAYS')
        now = datetime.now()
        query_end = int(now.timestamp())
        query_start = int((now - timedelta(days=delta)).timestamp())

        attributes = [{'AttributeKey': 'ReadOnly', 'AttributeValue': f'{read_only}'}]

        try:
            client = session.client('cloudtrail')
            paginator = client.get_paginator('lookup_events')

            pages = paginator.paginate(LookupAttributes=attributes, StartTime=query_start, EndTime=query_end, EventCategory='insight')
            for page in pages:
                # records.appned(page.get(SOMEEVENT))
                pass # Logic


        except Exception as err:
            self.framework.print_error(f'Error during ReadOnly cloudtrail:LookupEvents call: {err}')

        return records


    def run(self):

        
        self.framework.print_status('Starting query for ReadOnly CloudTrail Insights events')
        all_records = self.fetch_records(True)

        self.framework.print_status('Starting query for non-ReadOnly CloudTrail Insights events')
        all_records.extend(self.fetch_records(False))

        for event in all_records:
            print(event)



        return None