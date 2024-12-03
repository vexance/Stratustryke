from stratustryke.core.module import AWSModule
from stratustryke.core.lib import StratustrykeException
from datetime import datetime, timedelta
import json

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
        self._options.add_string('PRINCIPAL_ARN', 'When supplied, filter output on the set Principal ARN(s) [S/F/P]', False)

        self.trail_events = {}


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
    

    def fetch_records(self, read_only: bool) -> bool:
        '''Paginate through CloudTrail events'''
        session = self.get_cred().session()
        
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
                events = [json.loads(e.get('CloudTrailEvent', {})) for e in page.get('Events', [])]

                for event in events:

                    principal_type = event.get('userIdentity', {}).get('type', None)
                    if principal_type != 'AssumedRole':
                        principal = event.get('userIdentity', {}).get('arn', None)
                        #role_session = ''
                    else:
                        principal = event.get('userIdentity', {}).get('sessionContext', {}).get('sessionIssuer', {}).get('arn', None)
                        # arn = event.get('userIdentity', {}).get('arn', '')
                        # role_session = f'({arn[arn.rfind("/")+1::]}) '

                    event_source = event.get('eventSource', None)
                    event_name = event.get('eventName', None)
                    #region = event.get('awsRegion', None)
                    error_code = event.get('errorCode', None)

                    if not all([principal, event_source, event_name]): continue

                    service = event_source[0:event_source.find('.')]
                    if error_code == None: prefix = '[+]'
                    elif error_code == 'AccessDenied': prefix = f'[-]({error_code}) '
                    else: prefix = f'[!]({error_code}) '
                    
                    msg = f'{prefix}PRINCIPAL_ARN called {service}:{event_name}'
                    #msg = f'{prefix} PRINCIPAL_ARN {role_session}called {service}:{event_name}'
                    #if region: msg = f'{msg} in {region}'

                    if principal not in self.trail_events.keys(): self.trail_events[principal] = set([msg])
                    else: self.trail_events[principal].add(msg)
                
        except Exception as err:
            self.framework.print_error(f'Error during cloudtrail:LookupEvents call: {err}')
            return False
        
        return True


    def run(self):       
        self.framework.print_status('Starting query for ReadOnly CloudTrail Insights events')
        self.fetch_records(True)

        if not self.get_opt('ONLY_READ'):
            self.framework.print_status('Starting query for non-ReadOnly CloudTrail Insights events')
            self.fetch_records(False)

        principals = self.lines_from_string_opt('PRINCIPAL_ARN', unique=True)
        if principals == None: principals = [f'{key}' for key in self.trail_events.keys()]

        for arn in principals:
            events = self.trail_events.get(arn, set())
            event_list = list(events)

            for event in event_list:
                msg = event[3::]
                msg = msg.replace('PRINCIPAL_ARN', arn)
                prefix = event[0:3]

                if prefix == '[+]': self.framework.print_success(msg)
                elif prefix == '[-]': self.framework.print_failure(msg)
                else: self.framework.print_warning(msg)
            

        return None