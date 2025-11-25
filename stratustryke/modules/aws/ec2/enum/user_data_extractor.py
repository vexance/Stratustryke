
from base64 import b64decode
from pathlib import Path
from re import fullmatch

from stratustryke.core.module.aws import AWSModule
from stratustryke.lib import module_data_dir
from stratustryke.settings import AWS_DEFAULT_ENABLED_REGIONS


class Module(AWSModule):

    OPT_DOWNLOAD_DIR = 'DOWNLOAD_DIR'
    OPT_NO_DOWNLOAD = 'NO_DOWNLOAD'
    OPT_ONLY_RUNNING = 'ONLY_RUNNING'
    OPT_TARGET_INSTANCE = 'TARGET_INSTANCE'
    OPT_INDIVIDUAL_CALLS = 'INDIVIDUAL_CALLS'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Exfiltrate lambda source code from accessible functions',
            'Details': 'Describe lambda function(s), then attempts to use the caller\'s credentials to retrieve the source code for target functions or all functions if not supplied',
            'References': [ '' ]
        }

        self._options.add_string(Module.OPT_DOWNLOAD_DIR, 'Directory files will be downloaded to', True, module_data_dir(self.name))
        self._options.add_boolean(Module.OPT_NO_DOWNLOAD, 'When enabled, disables source code download and only enumerates configs', True, False)
        self._options.add_boolean(Module.OPT_ONLY_RUNNING, 'When enabled, limits output to only those EC2s currently running', True, False)

        self._advanced.add_string(Module.OPT_TARGET_INSTANCE, 'When set, only attempt ec2:DescribeInstances on the target id(s)/arn(s)', False)
        self._advanced.add_boolean(Module.OPT_INDIVIDUAL_CALLS, 'When enabled and targets specified, perform describe operations individually (useful when permissions are unknown)', False, False)


    @property
    def search_name(self):
        return f'aws/ec2/enum/{self.name}'
    

    def describe_instances(self, region: str, targets: str | list[str] | None) -> list:
        session = self.get_cred().session(region)
        account = self.get_cred().account_id
        only_running = self.get_opt(Module.OPT_ONLY_RUNNING)
        describe_filter = [{"Name": "instance-state-name","Values": ["running"]}] if only_running else []

        ret = [] # will contain just the instance ids
        try:
            client = session.client('ec2')
            paginator = client.get_paginator('describe_instances')

            if targets == None: # get all instances
                paginator = client.get_paginator('describe_instances')
                pages = paginator.paginate(Filters=describe_filter)

            else: # just describing specified instance(s)
                if isinstance(targets, str): targets = [targets]
                page = client.describe_instances(InstanceIds=targets, Filters=describe_filter)
                pages = [page]


        except Exception as err:
            self.print_failure(f'Failed to perform ec2:DescribeInstances call in {region}')
            if self.verbose: self.print_error(f'{err}')
            return []
        
        
        instances = []
        for page in pages:
            reservations = page.get('Reservations', [])
            for r in reservations: instances.extend(r.get('Instances', []))
        
        for i in instances:
            # Instance Id / derive instance ARN
            i_id = i.get('InstanceId', None)
            if i_id == None: continue
            i_arn = f'arn:aws:ec2:{region}:{account}:instance/{i_id}'
            
            # Parse the tags
            tags = i.get('Tags', [])
            formatted_tags = {}
            for tag in tags:
                key = tag.get('Key', None)
                val = tag.get('Value', None)

                formatted_tags[key] = val

            # Instance State
            i_state = i.get('State', {}).get('Name', 'unknown')
            if only_running and i_state != 'running': continue 

            # Show we've found the instance, if a name is assigned we'll display that too
            i_name = formatted_tags.get('Name', None)
            prefix = 'Found Instance' if (i_name == None) else f'Found ({i_state}) instance \'{i_name}\''
            self.print_success(f'{prefix} {i_arn}')

            # Print tags if VERBOSE is on
            if self.verbose and (len(formatted_tags.keys()) > 0):
                self.print_status(f'({i_id}) Instance Tags: {formatted_tags}')

            # Obtain / show IAM role association
            iam_role = i.get('IamInstanceProfile', {}).get('Arn', None)
            if self.verbose and (iam_role != None):
                self.print_status(f'({i_id}) Instance Profile: {iam_role}')

            # Show assigned key at launch
            key_name = i.get('KeyName', None)
            if self.verbose and (key_name != None):
                self.print_status(f'({i_id}) Keypair Name: {key_name}')

            ret.append(i_id)

        return ret


    def get_user_data(self, region: str, instance_id: str) -> None:
        session = self.get_cred().session(region)

        try:
            client = session.client('ec2')
            res = client.describe_instance_attribute(InstanceId=instance_id, Attribute='userData')

            user_data = res.get('UserData', {}).get('Value', None)
        
        except Exception as err:
            self.print_failure(f'Unable to retrieve user data for instance {instance_id}')
            if self.verbose: self.print_error(f'{err}')
            return None
        
        return user_data
        
    
    def parse_target_instances(self, targets: list[str]) -> dict:

        INSTANCE_ID_REGEX = r'i-(?:[0-9a-f]{8}|[0-9a-f]{17})'
        INSTANCE_ARN_REGEX = r'arn:(?:aws|aws-us-gov|aws-cn):ec2:[a-z0-9-]+:\d{12}:instance/i-(?:[0-9a-f]{8}|[0-9a-f]{17})'

        ret = {}
        for target in targets:
            if fullmatch(INSTANCE_ARN_REGEX, target):
                region = target.split(':')[3]
                instance_id = target.split('/')[1]
                
                if region not in ret.keys(): ret[region] = set()
                ret[region].add(instance_id)

            elif fullmatch(INSTANCE_ID_REGEX, target):
                if '__DEFAULT__' not in ret.keys(): ret['__DEFAULT__'] = set()
                ret['__DEFAULT__'].add(target)

            else:
                if self.verbose: self.print_warning(f'Target {target} is not an EC2 instance ARN or identifier, skipping...')


        if '__DEFAULT__' in ret.keys():
            ids = ret.pop('__DEFAULT__')
            for region in AWS_DEFAULT_ENABLED_REGIONS: ret[region] = ret[region] | ids
            
        
        return ret


    def write_user_data(self, instance_id: str, content: str) -> None:
        '''Save user data for an instance to a file'''
        content = b64decode(content).decode('utf-8')

        try:
            download_path = str(Path(self.get_opt(Module.OPT_DOWNLOAD_DIR)).resolve().absolute())
            with open(f'{download_path}/{instance_id}.txt', 'w') as file:
                file.write(content)

            self.print_success(f'Wrote user data to {download_path}/{instance_id}.txt')

        except Exception as err:
            self.print_failure(f'Error writing user data for instance {instance_id}')
            if self.verbose: self.print_error(str(err))
        
        return None


    def run(self) -> None:

        targets = self.get_opt_multiline(Module.OPT_TARGET_INSTANCE)
                
        # ec2:DescribeInstances for all
        if targets == None:
            if self.verbose: self.print_status('No targets specified, attempting to retrieve all instances...')

            for region in self.get_regions():
                

                instances = self.describe_instances(region)
                
                for instance in instances:
                    content = self.get_user_data(region, instance)

                    if content != None: self.write_user_data(instance, content)
                    
                    else: self.print_warning(f'No user data found for {instance}')
            

        # Target Arns / Ids specified
        else:
            targets = self.parse_target_instances(targets)
            individual_calls = self.get_opt(Module.OPT_INDIVIDUAL_CALLS)

            for region, target_ids in targets.keys():
                self.print_status(f'Enumerating information for target instances in {region}...')

                if individual_calls: # One-by-one in case we can describe some, but not all
                    for target in target_ids: self.describe_instances(region, target_ids=target)

                else: instances = self.describe_instances(region, target_ids=list(target_ids))

                # Likely poor handling for instances that don't exist. But whatever...
                # Todo: come back to this and skip instances that didn't have a describe call response?
                for target in target_ids:
                    content = self.get_user_data(region, target)
                    if content != None: self.write_user_data(instance, content)
                    else: self.print_warning(f'No user data found for {instance}')


        return None
