
from re import fullmatch

from stratustryke.core.module.aws import AWSModule
from stratustryke.settings import on_linux
from stratustryke.lib.regex import AWS_ROLE_ARN_REGEX


class Module(AWSModule):

    OPT_SKIP_IMPORT = 'SKIP_IMPORT'
    OPT_ALIAS = 'ALIAS'
    OPT_WORKSPACE = 'WORKSPACE'
    OPT_TARGET_ROLE = 'TARGET_ROLE'
    OPT_EXTERNAL_ID = 'EXTERNAL_ID'
    OPT_DURATION = 'DURATION'
    OPT_SESSION_NAME = 'SESSION_NAME'


    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Create new AWS credstore credential via sts:AssumeRole call',
            'Details': 'Performs an sts:AssumeRole call with the supplied options. Optionally, import the credentials into the stratustryke credstore',
            'References': ['']
        }

        self._options.add_string(Module.OPT_ALIAS, 'Override / prefix for the name of the cred alias for import', False)
        self._options.add_string(Module.OPT_TARGET_ROLE, 'Target ARN/Name of role to assume', True)
        self._options.add_string(Module.OPT_EXTERNAL_ID, 'External Id, if necessary, to use in the call', False, sensitive=True) # can sometimes be sensitive, so we'll play it safe
        self._options.add_string(Module.OPT_SESSION_NAME, 'Name to designate for the assumed role session', False, 'stratustryke')

        self._advanced.add_boolean(Module.OPT_SKIP_IMPORT, 'When enabled, do not import the credential', False, False)
        self._advanced.add_integer(Module.OPT_DURATION, 'Time (minutes | 15-60) for session to be valid for [defaut: 50]', True, 30)
        self._advanced.add_string(Module.OPT_WORKSPACE, 'Workspace for cred import [framework default when unset]', True, self.framework._config.get_val(Module.OPT_WORKSPACE))


    @property
    def search_name(self):
        return f'aws/sts/util/{self.name}'
    

    def get_role_arns(self, default_account_id: str) -> list:
        '''Iterate through arns; return full ARN in the caller's region if a suspected name was provided'''
        provided_arn = self.get_opt_multiline(Module.OPT_TARGET_ROLE)
        ret = []

        for entry in provided_arn:
            if not fullmatch(AWS_ROLE_ARN_REGEX, entry):
                interpretted_arn = f'arn:aws:iam::{default_account_id}:role/{entry}'
                self.print_warning(f'Interpreting {entry} as {interpretted_arn}')
                ret.append(interpretted_arn)
            else:
                ret.append(entry)

        if len(ret) > 1:
            self.print_status(f'Ingested {len(ret)} targets')

        return ret


    def derive_alias(self, arn: str, prefixed: bool) -> str:
        '''Determine what alias to give the cred object based off the ARN and module options'''
        alias = self.get_opt(Module.OPT_ALIAS)

        # arn:aws:iam::ACCOUNT_NUMBER:role/ROLE_NAME
        role_name = arn.split('/')[1]

        if prefixed:
            return f'{alias}_{role_name}' if alias != None else role_name
        else:
            return alias if alias != None else role_name


    def run(self):
        cred = self.get_cred()
        workspace = self.get_opt(Module.OPT_WORKSPACE)
        ext_id = self.get_opt(Module.OPT_EXTERNAL_ID)
        duration = self.get_opt(Module.OPT_DURATION)
        session_name = self.get_opt(Module.OPT_SESSION_NAME)
        region = self.get_opt(Module.OPT_AWS_REGION)

        skip_import = self.get_opt(Module.OPT_SKIP_IMPORT)
        arns = self.get_role_arns(cred.account_id)
        alias_prefixed = len(arns) > 1

        for arn in arns:
            try:
                cred_alias = self.derive_alias(arn, alias_prefixed)
                assumed_role_cred = cred.assume_role(arn, ext_id=ext_id, duration=duration, region=region, session_name=session_name, workspace=workspace, alias=cred_alias)
                
                if skip_import: # Just print that it succeeded
                    self.print_success(f'Successfully performed sts:AssumeRole for {arn}')
                else: # Add to cred db; should print itself anyway
                    self.framework.credentials.store_credential(assumed_role_cred)

                if self.verbose: # print creds to be copy/pasted into env vars
                    env_prefix = 'export ' if on_linux else '$Env:'

                    self.print_line(f'{env_prefix}AWS_ACCESS_KEY_ID={assumed_role_cred._access_key_id}')
                    self.print_line(f'{env_prefix}AWS_SECRET_ACCESS_KEY={assumed_role_cred._secret_key}')
                    self.print_line(f'{env_prefix}AWS_SESSION_TOKEN={assumed_role_cred._session_token}')
                
            except Exception as err:
                self.print_failure(f'Failed to sts:AssumeRole on {arn}')
                if self.verbose: self.print_failure(str(err))
        
        return None
    
