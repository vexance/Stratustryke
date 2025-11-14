from stratustryke.core.module import AWSModule
from pathlib import Path
from stratustryke.core.lib import StratustrykeException, module_data_dir
from base64 import b64decode


class Module(AWSModule):

    OPT_DOWNLOAD_DIR = 'DOWNLOAD_DIR'
    OPT_NO_DOWNLOAD = 'NO_DOWNLOAD'
    OPT_ONLY_RUNNING = 'ONLY_RUNNING'

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


    @property
    def search_name(self):
        return f'aws/ec2/enum/{self.name}'
    
    def describe_instances(self, instance_id: str = None) -> list:
        session = self.get_cred().session()
        account = self.get_cred().account_id
        VERBOSE = self.get_opt(Module.OPT_VERBOSE)
        region = self.get_opt(Module.OPT_AWS_REGION)
        only_running = self.get_opt(Module.OPT_ONLY_RUNNING)

        ret = []

        try:
            client = session.client('ec2')
            paginator = client.get_paginator('describe_instances')

            if instance_id == None: # get all instances
                paginator = client.get_paginator('describe_instances')
                pages = paginator.paginate()

            else: # just describing one instance
                page = client.describe_instances(InstanceIds=[instance_id])
                pages = [page]


        except Exception as err:
            self.framework.print_failure(f'Failed to perform ec2:DescribeInstances call')
            self.framework.print_error(f'{err}')
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
            i_state = i.get('State', {}).get('Name', None)
            if only_running and i_state != 'running': continue 

            # Show we've found the instance, if a name is assigned we'll display that too
            i_name = formatted_tags.get('Name', None)
            prefix = 'Found Instance' if (i_name == None) else f'Found ({i_state}) instance \'{i_name}\''
            self.framework.print_success(f'{prefix} {i_arn}')

            # Print tags if VERBOSE is on
            if VERBOSE and (len(formatted_tags.keys()) > 0):
                self.framework.print_status(f'({i_id}) Instance Tags: {formatted_tags}')

            # Obtain / show IAM role association
            iam_role = i.get('IamInstanceProfile', {}).get('Arn', None)
            if VERBOSE and (iam_role != None):
                self.framework.print_status(f'({i_id}) IAM Association: {iam_role}')

            # Show assigned key at launch
            key_name = i.get('KeyName', None)
            if VERBOSE and (key_name != None):
                self.framework.print_status(f'({i_id}) Keypair Name: {key_name}')

            ret.append(i_id)

        return ret


    def get_user_data(self, instance_id: str) -> None:
        session = self.get_cred().session()

        try:
            client = session.client('ec2')
            res = client.describe_instance_attribute(InstanceId=instance_id, Attribute='userData')

            user_data = res.get('UserData', {}).get('Value', None)
            return user_data
        
        except Exception as err:
            self.framework.print_failure(f'Unable to retrieve user data for instance {instance_id}')
            self.framework.print_error(f'{err}')
            return None
        
    
    def run(self) -> None:

        instances = self.describe_instances()
        
        for instance in instances:
            content = self.get_user_data(instance)

            if content != None:

                content = b64decode(content).decode('utf-8')

                try:
                    download_path = str(Path(self.get_opt(Module.OPT_DOWNLOAD_DIR)).resolve().absolute())
                    with open(f'{download_path}/{instance}.txt', 'w') as file:
                        file.write(content)

                    self.framework.print_success(f'Wrote user data to {download_path}/{instance}.txt')

                except Exception as err:
                    self.framework.print_error(f'Error writing user data: {err}')
            
            else:
                self.framework.print_status(f'No user data found for {instance}')

                

