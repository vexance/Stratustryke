
import threading

from datetime import datetime, timedelta
from pathlib import Path
from time import sleep

from stratustryke.core.module.aws import AWSModule
from stratustryke.lib import StratustrykeException


class Module(AWSModule):

    OPT_MAX_QUERIES = 'MAX_QUERIES'
    OPT_POLL_DELAY = 'POLL_DELAY'
    OPT_RECORD_LIMIT = 'RECORD_LIMIT'
    OPT_TIMEDELTA = 'TIMEDELTA_DAYS'
    OPT_OUTPUT_DIR = 'OUTPUT_DIR'    
    OPT_SEARCH_PATTERN = 'SEARCH_PATTERN'

    OPT_LOG_ACCOUNTS = 'LOG_ACCOUNTS'
    OPT_LOG_PREFIXES = 'LOG_PREFIXES'


    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Details': 'Performs Logs Insights queries within CloudWatch for log groups to download records which match the searched patterns within the message',
            'Description': 'Query CloudWatch via Logs Insights and download resulting log records',
            'References': ['']
        }
        
        self._options.add_integer(Module.OPT_RECORD_LIMIT, 'Limit on number of log records returned by the queries', True, 1000)
        self._options.add_integer(Module.OPT_TIMEDELTA, 'Number of days back to include within queries', True, 14)
        self._options.add_string(Module.OPT_OUTPUT_DIR, 'Directory to save query results to', True, '.')
        self._options.add_string(Module.OPT_SEARCH_PATTERN, 'Regular expression used to filter log message contents (f/p)', True)
        
        self._advanced.add_string(Module.OPT_LOG_ACCOUNTS, 'Target AWS account(s) to query logs from (f/p)', False)
        self._advanced.add_string(Module.OPT_LOG_PREFIXES, 'When supplied, filter log groups selected in the account(s) (f/p)', False)
        self._advanced.add_integer(Module.OPT_POLL_DELAY, 'Seconds to wait before re-checking query status (1 - 300)', True, 5)
        self._advanced.add_integer(Module.OPT_MAX_QUERIES, 'Maximum queries to que simultaneously (max: 30)', True, 5)
        # Potential advanced option?? QUERY_TEMPLATE to define the query syntax and where to inject SEARCH_PATTERN into


    @property
    def search_name(self):
        return f'aws/cloudwatch/enum/{self.name}'

    
    def validate_options(self) -> tuple:
        valid, msg = super().validate_options()
        if not valid:
            return (False, msg)

        output_dir = self.get_opt(Module.OPT_OUTPUT_DIR)
        output_dir = Path(output_dir).resolve().absolute()
        if not (output_dir.exists() and output_dir.is_dir()):
            return (False, f'Download directory does not exist: {output_dir}')
        
        max_queries = self.get_opt(Module.OPT_MAX_QUERIES)
        if max_queries > 30 or max_queries < 1:
            return (False, f'Number of maximum queries supplied, {max_queries}, is more than 30 or less than 1')
        
        delay = self.get_opt(Module.OPT_POLL_DELAY)
        if delay < 1 or delay > 300:
            return (False, f'Polling delay \'{delay}\' should be within 1 to 300 seconds')
        
        return (True, None)


    def perform_and_monitor_query(self, region: str, pattern: str, start: int, end: int, query_num: int) -> bool:
        '''Starts a logs insights queries and waits until the query has completed before retrieving results and writing to a file'''
        
        delay = self.get_opt(Module.OPT_POLL_DELAY)
        out_dir = self.get_opt(Module.OPT_OUTPUT_DIR)
        record_limit = self.get_opt(Module.OPT_RECORD_LIMIT)

        account_ids = self.get_opt_multiline(Module.OPT_LOG_ACCOUNTS)
        log_prefixes = self.get_opt_multiline(Module.OPT_LOG_PREFIXES)

        source = 'SOURCE logGroups('
        if account_ids: source += f'accountIdentifiers:{account_ids}'
        if account_ids and log_prefixes: source +', '
        if log_prefixes: source += f'namePrefix:{log_prefixes}'
        source += ')'

        query = f'{source} | filter @message like /{pattern}/ | sort @timestamp desc | fields @log, @message'
        query_id = None

        try:
            client = self.get_cred().session(region).client('logs')


            res = client.start_query(queryString=query, startTime=start, endTime=end, limit=record_limit)
            query_id = res.get('queryId', None)
            if query_id == None:
                raise StratustrykeException(f'Unable retrieve query id from logs:StartQuery request: {res}')
            
            self.print_status(f'Started query for pattern {pattern}: {query_id}')

        except Exception as err:

            if 'No log groups were found for the query' in str(err):
                attempted_source = source[17:-1] # source[17:-1] is everything in between 'SOURCE logGroups(' and ')'
                if attempted_source == '': attempted_source = f'caller\'s account ({self.get_cred().account_id})'
                self.print_warning(f'No matching log groups found in {region} for {attempted_source}') 

            else:
                self.print_failure(f'Exception thrown during logs:StartQuery in {region} for \'{query}\'')
                if self.verbose: self.print_error(f'{err}')
            
            return False

        try:
            poll = {'status': 'Running'}
            while poll.get('status', None) == 'Running':
                sleep(delay)

                poll = client.get_query_results(queryId=query_id)

            # Parsing results
            lines = []
            for entry in poll.get('results', []):
                lg_name, message = None, None
                for field in entry:
                    field_name = field.get('field', None)
                    if field_name == '@log': lg_name = field.get('value', None)
                    if field_name == '@message': message = field.get('value', None)

                if not all ([lg_name, message]): continue

                else:
                    if self.verbose: self.print_line(f'({lg_name}) {message}')
                    lines.append(f'({lg_name}) {message}')

        except Exception as err:
            self.print_failure(f'Exception thrown during logs:GetQueryResults in {region} for query {query_id}')
            if self.verbose: self.print_error(f'{err}')
            return False

        # Need to write to a file!
        if len(lines) > 0:
            outfile = f'{out_dir}/Stratustryke_LogsInsights_Query_{query_id}.txt'
            with open(Path(outfile), 'w') as file:
                file.write('\n'.join(lines))

            self.print_success(f'Saved {len(lines)} records matching /{pattern}/ to {outfile}')
        else:
            self.print_failure(f'No matching entries found for /{pattern}/')
        
        return True



    def run(self):

        max_queries = self.get_opt(Module.OPT_MAX_QUERIES)
        timedelta_days = self.get_opt(Module.OPT_TIMEDELTA)
        delay = self.get_opt(Module.OPT_POLL_DELAY)
        if delay < 1 or delay > 300:
            self.print_error(f'Polling delay \'{delay}\' should be within 1 to 300 seconds')
            return None
        
        # Multi-line supported options
        search_patterns = self.get_opt_multiline(Module.OPT_SEARCH_PATTERN)

        # Cast start / end times to linux epochs
        now = datetime.now()
        query_end = int(now.timestamp())
        query_start = int((now - timedelta(days=timedelta_days)).timestamp())

        for region in self.get_regions():

            threads, i = [], 0
            for pattern in search_patterns:
                threads.append(threading.Thread(target=self.perform_and_monitor_query, args=(region, pattern, query_start, query_end, i)))
                i += 1

            for thread in threads:
                active = threading.active_count()
                
                while active >= (max_queries + 1): # active_count() includes main thread
                    sleep(1)
                    active = threading.active_count()
                
                thread.start()

            for thread in threads: thread.join()

        return None 

        




        

