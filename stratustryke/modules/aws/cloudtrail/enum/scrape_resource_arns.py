
from datetime import datetime, timedelta
from re import findall

from stratustryke.core.module.aws import AWSModule


class Module(AWSModule):

    OPT_TIMEDELTA = 'TIMEDELTA_DAYS'
    OPT_SKIP_NONREAD = 'SKIP_NONREAD'
    ARN_SEARCH_REGEX = '(\"|\\s)(arn:aws:[a-z0-9]+:[a-z0-9\\-]*:(|[0-9]{12}):[^\\s\"]+)(\"|\\s)'

    def __init__(self, framework) -> None:
        super().__init__(framework)

        self._info = {
            'Authors': ['@vexance'],
            'Details': 'Inspects Cloudtrail logs and extracts referenced resource ARNs',
            'Description': 'Query events from CloudTrail insights and extract ARNs',
            'References': ['']
        }

        self._options.add_integer(Module.OPT_TIMEDELTA, 'Time period in days of events to include (1-90)', True, 14)
        self._options.add_boolean(Module.OPT_SKIP_NONREAD, 'When enabled, skips inspection of non-readonly events', True, False)


    @property
    def search_name(self):
        return f'aws/cloudtrail/enum/{self.name}'
    

    def validate_options(self) -> tuple:
        valid, msg = super().validate_options()
        if not valid:
            return (False, msg)
        
        delta = self.get_opt(Module.OPT_TIMEDELTA)
        if delta > 90 or delta < 1:
            return (False, 'Time delta must be between 1 and 90')

        return (True, None)
    

    def fetch_records(self, read_only: bool) -> list:
        '''Paginate through CloudTrail events'''
        session = self.get_cred().session()
        arns = []

        # Determine timeframe limits
        delta = self.get_opt(Module.OPT_TIMEDELTA)
        now = datetime.now()
        query_end = int(now.timestamp())
        query_start = int((now - timedelta(days=delta)).timestamp())

        attributes = [{'AttributeKey': 'ReadOnly', 'AttributeValue': f'{read_only}'.lower()}]

        try:
            client = session.client('cloudtrail')
            paginator = client.get_paginator('lookup_events')

            pages = paginator.paginate(LookupAttributes=attributes, StartTime=query_start, EndTime=query_end)
            self.print_status(f'Iterating through event pages...')

            for page in pages:
                events = str([e.get('CloudTrailEvent', {}) for e in page.get('Events', [])])
                matches = findall(Module.ARN_SEARCH_REGEX, events)
                for match in matches:
                    arns.append(match[1])
                    
        except Exception as err:
            self.print_error(f'Error during cloudtrail:LookupEvents call: {err}')
            return []
        
        self.print_status('Post-processing for uniqueness...')

        return arns


    def run(self):

        
        self.print_status('Starting query for ReadOnly CloudTrail Insights events')
        all_records = self.fetch_records(True)

        if not self.get_opt(Module.OPT_SKIP_NONREAD):
            self.print_status('Starting query for non-ReadOnly CloudTrail Insights events')
            all_records.extend(self.fetch_records(False))

        self.print_status('Post-processing for ARN uniqueness, this may take some time...')
        all_records = list(set(all_records))

        for arn in all_records:
            self.print_success(arn)

        return None