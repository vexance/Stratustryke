
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
    

    def fetch_records(self, region: str, read_only: bool) -> set:
        '''Paginate through CloudTrail events'''
        session = self.get_cred().session(region)
        arns = set()

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
            if self.verbose: self.print_status(f'Iterating through {region} event pages...')

            for page in pages:
                events = str([e.get('CloudTrailEvent', {}) for e in page.get('Events', [])])
                matches = findall(Module.ARN_SEARCH_REGEX, events)
                for match in matches:
                    arns.add(match[1]) # tuple at index 1 is the ARN value ('"', ARN, AccountId, '"')
                    
        except Exception as err:
            self.print_failure(f'Error during cloudtrail:LookupEvents call in region {region}')
            if self.verbose: self.print_error(str(err))
            return set()
        
        return arns


    def run(self):
        
        all_records = set()
        for region in self.get_regions():

            self.print_status(f'Inspecting CloudTrail events in {region}')
            regional_records = self.fetch_records(region, True)

            if not self.get_opt(Module.OPT_SKIP_NONREAD):
                if self.verbose: self.print_status(f'Starting search on non-ReadOnly events in {region}')
                regional_records = regional_records | self.fetch_records(region, False)

            self.print_status(f'Found {len(regional_records)} unqiue ARN patterns in {region}')
            all_records = all_records | regional_records # accumulate accross regions


        for arn in all_records:
            if arn.endswith('\\\\'): arn = arn[:-2] # odd case where this is a common trailing thing 
            self.print_success(arn)

        return None