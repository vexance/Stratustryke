from stratustryke.core.module import AWSModule
from stratustryke.core.lib import StratustrykeException
from datetime import datetime, timedelta
from re import findall

class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)

        self._info = {
            'Authors': ['@vexance'],
            'Details': 'Inspects Cloudtrail logs and extracts referenced resource ARNs',
            'Description': 'Query events from CloudTrail insights and extract ARNs',
            'References': ['']
        }

        self._options.add_integer('TIMEDELTA_DAYS', 'Time period in days of events to include (1-90)', True, 14)
        self._options.add_boolean('ONLY_READ', 'When enabled, skips inspection of non-readonly events', True, False)

        self._arn_search_regex = "(\"|\s)(arn:aws:[a-z0-9]+:[a-z0-9\-]*:(|[0-9]{12}):[^\s\"]+)(\"|\s)"



    @property
    def search_name(self):
        return f'aws/enum/authed/{self.name}'
    

    def validate_options(self) -> tuple:
        valid, msg = super().validate_options()
        if not valid:
            return (False, msg)
        
        delta = self.get_opt('TIMEDELTA_DAYS')
        if delta > 90 or delta < 1:
            return (False, 'Time delta must be between 1 and 90')

        return (True, None)
    

    def fetch_records(self, read_only: bool) -> list:
        '''Paginate through CloudTrail events'''
        session = self.get_cred().session()
        arns = []

        # Determine timeframe limits
        delta = self.get_opt('TIMEDELTA_DAYS')
        now = datetime.now()
        query_end = int(now.timestamp())
        query_start = int((now - timedelta(days=delta)).timestamp())

        attributes = [{'AttributeKey': 'ReadOnly', 'AttributeValue': f'{read_only}'.lower()}]

        try:
            client = session.client('cloudtrail')
            paginator = client.get_paginator('lookup_events')

            pages = paginator.paginate(LookupAttributes=attributes, StartTime=query_start, EndTime=query_end)
            self.framework.print_status(f'Iterating through event pages...')

            for page in pages:
                events = str([e.get('CloudTrailEvent', {}) for e in page.get('Events', [])])
                matches = findall(self._arn_search_regex, events)
                for match in matches:
                    arns.append(match[1])
                    
        except Exception as err:
            self.framework.print_error(f'Error during cloudtrail:LookupEvents call: {err}')
            return []
        
        self.framework.print_status('Post-processing for uniqueness...')

        return arns


    def run(self):

        
        self.framework.print_status('Starting query for ReadOnly CloudTrail Insights events')
        all_records = self.fetch_records(True)

        if not self.get_opt('ONLY_READ'):
            self.framework.print_status('Starting query for non-ReadOnly CloudTrail Insights events')
            all_records.extend(self.fetch_records(False))

        self.framework.print_status('Post-processing for ARN uniqueness, this may take some time...')
        all_records = list(set(all_records))

        for arn in all_records:
            self.framework.print_success(arn)

        return None