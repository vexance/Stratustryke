
from stratustryke.core.module import AWSModule
from stratustryke.core.lib import StratustrykeException
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
import threading


class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Details': 'Performs Logs Insights queries within CloudWatch for log groups to download records which match the searched patterns within the message',
            'Description': 'Query CloudWatch via Logs Insights and download resulting log records',
            'References': ['']
        }
        self._options.add_integer('MAX_QUERIES', 'Maximum number of queries to que simultaneously (max: 30)', True, 5)
        self._options.add_integer('POLL_DELAY', 'Number of seconds to wait before re-checking query status (1 - 300)', True, 5)
        self._options.add_integer('RECORD_LIMIT', 'Limit to impose on the number of log records returned by the queries', True, 1000)
        self._options.add_integer('TIMEDELTA_DAYS', 'Number of days back to include within queries', True, 14)
        self._options.add_boolean('VERBOSE', 'When enabled, prints matching records to framework interface [default: false]', True, False)
        self._options.add_string('OUTPUT_DIR', 'Directory to save query results to', True, '.')
        self._options.add_string('LOG_GROUPS', 'Names of log group(s) to include within the query (max 50). (F/P)', True)
        self._options.add_string('SEARCH_PATTERN', 'Regualr expression to use as the search term within log messages (F/P)')


        # Potential advanced option?? QUERY_TEMPLATE to define the query syntax and where to inject SEARCH_PATTERN into


    @property
    def search_name(self):
        return f'aws/enum/authed/{self.name}'

    
    def validate_options(self) -> tuple:
        valid, msg = super().validate_options()
        if not valid:
            return (False, msg)

        output_dir = self.get_opt('OUTPUT_DIR')
        output_dir = Path(output_dir).resolve().absolute()
        if not (output_dir.exists() and output_dir.is_dir()):
            return (False, f'Download directory does not exist: {output_dir}')
        
        lg_len = len(self.lines_from_string_opt('LOG_GROUPS', unique=True))
        if lg_len > 50 or lg_len < 1:
            return (False, f'Number of log groups supplied, {lg_len}, is more than 50 or less than 1')
        
        max_queries = self.get_opt('MAX_QUERIES')
        if max_queries > 30 or max_queries < 1:
            return (False, f'Number of maximum queries supplied, {max_queries}, is more than 30 or less than 1')
        
        delay = self.get_opt('POLL_DELAY')
        if delay < 1 or delay > 300:
            return (False, f'Polling delay \'{delay}\' should be within 1 to 300 seconds')
        
        return (True, None)


    def perform_and_monitor_query(self, pattern: str, start: int, end: int, query_num: int) -> bool:
        '''Starts a logs insights queries and waits until the query has completed before retrieving results and writing to a file'''
        
        delay = self.get_opt('POLL_DELAY')
        log_groups = self.lines_from_string_opt('LOG_GROUPS')
        verbose = self.get_opt('VERBOSE')
        out_dir = self.get_opt('OUTPUT_DIR')
        record_limit = self.get_opt('RECORD_LIMIT')
        query = f'fields @message, @log | sort @timestamp desc | filter @message like /{pattern}/'

        try:
            client = self.get_cred().session().client('logs')


            res = client.start_query(logGroupNames=log_groups, queryString=query, startTime=start, endTime=end, limit=record_limit)
            query_id = res.get('queryId', None)
            if query_id == None:
                raise StratustrykeException(f'Unable retrieve query id from logs:StartQuery request: {res}')
            
            self.framework.print_status(f'Started query for pattern {pattern}: {query_id}')

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
                    if field_name == '@log':
                        lg_name = field.get('value', None)

                    if field_name == '@message':
                        message = field.get('value', None)

                if not all ([lg_name, message]):
                    continue

                else:
                    if verbose: self.framework.print_line(f'{lg_name} - {message}')
                    lines.append(f'{lg_name} - {message}')

        except Exception as err:
            self.framework.print_error(f'Exception throwing when performing query \'{query}\'')
            self.framework.print_error(f'{err}')
            return False

        # Need to write to a file!
        if len(lines) > 0:
            outfile = f'{out_dir}/Stratustryke_LogsInsights_Query-{query_num}'
            with open(Path(outfile), 'w') as file:
                file.write('\n'.join(lines))

            self.framework.print_success(f'Saved {len(lines)} records matching /{pattern}/ to {outfile}')
        else:
            self.framework.print_failure(f'No matching entries found for pattern /{pattern}/')
        
        return True



    def run(self):
        max_queries = self.get_opt('MAX_QUERIES')
        timedelta_days = self.get_opt('TIMEDELTA_DAYS')
        delay = self.get_opt('POLL_DELAY')
        if delay < 1 or delay > 300:
            self.framework.print_error(f'Polling delay \'{delay}\' should be within 1 to 300 seconds')
            return None
        
        lg_count = len(self.lines_from_string_opt('LOG_GROUPS'))
        if lg_count > 49:
            self.framework.print_error(f'Number of log groups provided, {lg_count}, is more than the 50 log group threshold.')
            return None

        # Multi-line supported options
        search_pattern = self.lines_from_string_opt('SEARCH_PATTERN')

        # Cast start / end times to linux epochs
        now = datetime.now()
        query_end = int(now.timestamp())
        query_start = int((now - timedelta(days=timedelta_days)).timestamp())

        threads, i = [], 0
        for pattern in search_pattern:
            threads.append(threading.Thread(target=self.perform_and_monitor_query, args=(pattern, query_start, query_end, i)))
            i += 1

        for thread in threads:
            active = threading.active_count()
            
            while active >= (max_queries + 1): # active_count() includes main thread
                sleep(1)
                active = threading.active_count()
            
            thread.start()

        for thread in threads: thread.join()

        return 

        




        

