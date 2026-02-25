
import json

from pathlib import Path
from collections import OrderedDict

from stratustryke.core.module.aws import AWSModule
from stratustryke.lib import module_data_dir


class Module(AWSModule):

    OPT_DOWNLOAD_DIR = 'DOWNLOAD_DIR'
    OPT_NO_DOWNLOAD = 'NO_DOWNLOAD'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Extract Cloudformation template contents and stack parameters',
            'Details': 'Describe Cloudformation stacks(s), then attempt to retrieve stack definition and paramaeters',
            'References': [ '' ]
        }

        self._options.add_string(Module.OPT_DOWNLOAD_DIR, 'Directory files will be downloaded to', True, module_data_dir(self.name))
        self._options.add_boolean(Module.OPT_NO_DOWNLOAD, 'When enabled, disables source code download and only enumerates configs', True, False)

    
    @property
    def search_name(self):
        return f'aws/cloudformation/enum/{self.name}'
    

    def list_stacks(self, region: str) -> list:
        session = self.get_cred().session(region)
        stacks = []
        
        try:
            client = session.client('cloudformation')
            paginator = client.get_paginator('list_stacks')
            pages = paginator.paginate()


        except Exception as err:
            self.print_failure('Failure performing cloudformation:ListStacks call')
            if self.verbose: self.print_error(f'{err}')
            return []
        
        for page in pages:
            summaries = page.get('StackSummaries')
            for stack in summaries:
                name = stack.get('StackName', None)
                stacks.append(name)

        return stacks


    def describe_stacks(self, region: str, stack_name: str = None) -> dict:
        '''List and get stack metadata'''
        session = self.get_cred().session(region)
        ret = {}
        ### First we'll try cloudformation:DescribeStacks; if this fails we may need to list and then describe individualls

        try:
            client = session.client('cloudformation')\
            
            if stack_name == None:
                paginator = client.get_paginator('describe_stacks')
                pages = paginator.paginate()
            
            else:
                page = client.describe_stacks(StackName=stack_name)
                pages = [page]
        
        except Exception as err:
            self.print_failure(f'Could not call cloudformation:DescribeStacks for stack \'{stack_name}\'')
            if self.verbose: self.print_error(f'{err}')
            return None


        for page in pages:
            stacks = page.get('Stacks', [])

            for stack in stacks:
                stack_id = stack.get('StackId', None)
                name = stack.get('StackName', None)

                self.print_success(f'Found {stack_id}')

                description = stack.get('Description', None)
                if self.verbose and (not (description == None or description == '')):
                    self.print_status(f'({name}) Description: {description}')

                # Inspect Stack Parameters
                parameters = stack.get('Parameters', [])
                formatted_params = {}
                for param in parameters:
                    key = param.get('ParameterKey', None)
                    val = param.get('ParameterValue', None)
                    resolved = param.get('ResolvedValue', None)

                    value = val if (resolved == None) else f'{val} (ResolvedValue: {resolved})'

                    formatted_params[key] = value

                if self.verbose and (len(formatted_params.keys()) > 0):
                    self.print_status(f'({name}) Stack Parameters: {formatted_params}')

                # Inspect stack Tags
                tags = stack.get('Tags', [])
                formatted_tags = {}
                for tag in tags:
                    key = tag.get('Key', None)
                    val = tag.get('Value', None)

                    formatted_tags[key] = val

                if self.verbose and (len(formatted_tags.keys()) > 0):
                    self.print_status(f'({name}) Stack Tags: {formatted_tags}')

                ret[name] = stack_id

        return ret
    

    def get_stack_template(self, region: str, stack_name: str, stack_id: str) -> bool:
        session = self.get_cred().session(region)
        download_dir = self.get_opt(Module.OPT_DOWNLOAD_DIR)

        try:
            client = session.client('cloudformation')
            res = client.get_template(StackName=stack_id)

            content = res.get('TemplateBody')
        
        except Exception as err:
            self.print_failure(f'Error retriving stack template for {stack_id}')
            if self.verbose: self.print_error(f'{err}')

        
        

        try:
            download_path = str(Path(download_dir).resolve().absolute())

            if isinstance(content, OrderedDict):
                content = json.dumps(dict(content), indent=4)
                ext = 'json'
            else: ext = 'yaml'

            with open(f'{download_path}/{stack_name}.{ext}', 'w') as file:
                file.write(content)

            self.print_success(f'Wrote template to {download_dir}/{stack_name}.{ext}')
            return True
        
        except Exception as err:
            self.print_error(f'Couldn\'t write stack template for {stack_name}: {err}')
            return False


    def run(self) -> None:

        regions = self.get_regions()
        # First, just attempt to describe all stacks
        
        for region in regions:
            stacks = self.describe_stacks(region)

            # First get all the metadata with regards to the stacks while collecting stack ARNs/Ids
            if stacks == {}: self.print_status('No cloudformation stacks found')
            elif stacks == None:
                self.print_status('cloudformation:DescribeStacks failed, attempting to perform cloudformation:ListStacks call')
                stack_names = self.list_stacks(region)

                for stack in stack_names:
                    ret = self.describe_stacks(region, stack)
                    stacks[stack] = ret[stack]

            # Now we'll iterate through the ARNs and download the stack templates
            for stack in stacks.keys():
                stack_arn = stacks[stack]

                self.get_stack_template(region, f'{stack}', stack_arn)
        