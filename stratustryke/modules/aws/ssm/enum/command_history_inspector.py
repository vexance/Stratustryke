
from datetime import datetime, timezone, timedelta

from stratustryke.core.module.aws import AWSModule
# from stratustryke.lib import module_data_dir


class Module(AWSModule):

    OPT_DOWNLOAD_DIR = 'DOWNLOAD_DIR'
    OPT_NO_DOWNLOAD = 'NO_DOWNLOAD'
    SSM_DOC = 'DOCUMENT_NAME'
    MAX_ITEMS = 'MAX_ITEMS'
    TIMEDELTA = 'TIMEDELTA_DAYS'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Inspect parameters passed to ssm run commands',
            'Details': 'Iterates over ssm run command history, inspecting parameters passed into the run command call. Also includes S3 output location when the VERBOSE flag is set.',
            'References': [ '' ]
        }

        self._options.add_string(Module.SSM_DOC, 'SSM document name used to filter command history', True, 'AWS-RunShellScript')
        self._options.add_integer(Module.MAX_ITEMS, 'Maximum number of commands, per region, to inspect [100k if unset]', False, 10000)
        self._options.add_integer(Module.TIMEDELTA, 'Specifies the maximum number of days back to inspect history', False, None)


    @property
    def search_name(self):
        return f'aws/ssm/enum/{self.name}'
    

    def resolve_filter_args(self) -> list:
        '''Produces the list of filters passed into the ssm:ListCommands operation'''
        days = self.get_opt(Module.TIMEDELTA)
        docfilter = self.get_opt(Module.SSM_DOC)
        
        filters = []
    
        if days is not None:
            utc_now = datetime.now(timezone.utc)
            timestamp = utc_now - timedelta(days=days)
            after = timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
            filters.append({'key': 'InvokedAfter', 'value': after})


        if docfilter is None:
            self.print_error(f'{Module.SSM_DOC} is a required module option')
            raise Exception(f'Missing required option {Module.SSM_DOC}')
        
        docfilter = docfilter.split(',')
        for item in docfilter:
            filters.append({'key': 'DocumentName', 'value': item})

        return filters


    def run(self) -> None:

        regions = self.get_regions()
        # First, just attempt to describe all stacks
        
        for region in regions:
            max_items = self.get_opt(Module.MAX_ITEMS) or 100000
            filters = self.resolve_filter_args()

            self.print_status(f'Inspecting ssm command history in region {region}')
            try:
                client = self.get_cred().session(region).client('ssm')
                next_token = ''
                inspected_items = 0
                
                args = {
                    'Filters': filters,
                }

                while next_token is not None and inspected_items < max_items:
                    if next_token != '': args['NextToken'] = next_token
                    res = client.list_commands(**args)

                    for c in res.get('Commands', []):
                        cmd_id = c.get('CommandId')
                        params = c.get('Parameters', {})

                        for key, val in params.items():
                            self.print_success(f'({region}:{cmd_id}) {key}: {val}')
                        
                        if self.verbose:
                            out_bucket = c.get('OutputS3BucketName', None)
                            out_prefix = c.get('OutputS3KeyPrefix', None)
                            if out_bucket is not None and out_prefix is not None:
                                self.print_status(f'({region}:{cmd_id}) S3 Output prefix: s3://{out_bucket}')
                        
                        inspected_items += 1
                        if not (inspected_items < max_items):
                            break

                    next_token = res.get('NextToken', None)

                if inspected_items < 1:
                    self.print_failure(f'No commands matching supplied filters found in region {region}')


            except Exception as err:
                self.print_warning(f'Uncaught exception inspecting command history in {region}')
                if self.verbose: self.print_error(err)

