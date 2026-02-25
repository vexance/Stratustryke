
import sqlite3
import logging
import collections.abc

from pathlib import Path

from stratustryke.core.credential import Credential, CloudCredential, GenericCredential, APICredential
from stratustryke.core.credential.aws import AWSCredential
from stratustryke.core.credential.microsoft import MicrosoftCredential
from stratustryke.core.credential.gcp import GCPCredential
from stratustryke.core.module.aws import AWSModule
from stratustryke.core.module.microsoft import MicrosoftModule


class CredentialStoreConnector(collections.abc.Mapping):
    def __init__(self, framework, conn_str: str) -> None:
        self._framework = framework
        self._conn_str = conn_str
        self._logger = logging.getLogger('stratustryke.credstore')
        self._creds = {}

        self._conn = self.connect_credstore(self._conn_str)

        if self._conn != None:        
            self.load_credentials()   

    def __getitem__(self, key):
        return self._creds[key]

    def __iter__(self):
        return iter(self._creds)

    def __len__(self):
        return len(self._creds)


    def connect_credstore(self, conn_str: str):
        conn_path = Path(conn_str)
        if conn_path.exists() and conn_path.is_file():
            # attempt to create the sqlite connection
            conn = sqlite3.connect(conn_str)
            self._logger.info(f'Connected to sqlite database at: {conn_path}')
        else: # we'll need to initialize it
            self._logger.info(f'Initializing credstore sqlite database at: {conn_path}')
            conn = sqlite3.connect(conn_str)
            cursor = conn.cursor()
            res = cursor.execute('CREATE TABLE stratustryke (alias TEXT PRIMARY KEY, cred_type TEXT NOT NULL, workspace TEXT NOT NULL, as_str TEXT NOT NULL);')
            cursor.close()

        return conn


    def load_credentials(self):
        '''Read the rows from the database table and create associated credentials objects'''
        cursor = self._conn.cursor()

        try:
            res = cursor.execute('SELECT alias, cred_type, workspace, as_str FROM stratustryke;')
        except Exception as err:
            self._logger.error(f'Exception thrown while loading credentials from credstore')
            self._logger.error(f'{err}')
            self._framework.print_warning('Unable to load credentials from stratustryke credstore')
            return {}
            
        for result in res.fetchall():
            if len(result) != 4:
                continue
            alias = result[0]
            cred_type = result[1]
            workspace = result[2]
            str_rep = result[3]
            if cred_type == 'Generic':
                cred = GenericCredential(alias, workspace, from_dict=str_rep)
            elif cred_type == 'API':
                cred = APICredential(alias, workspace, from_dict=str_rep)
            elif cred_type == 'AWS':
                cred = AWSCredential(alias, workspace, from_dict=str_rep)
            elif cred_type == 'MSFT':
                cred = MicrosoftCredential(alias, workspace, from_dict=str_rep)
            elif cred_type == 'GCP':
                cred = GCPCredential(alias, workspace, from_dict=str_rep)
            else:
                self._logger.error(f'Could not import credential {alias} due to unsupported credential type: {cred_type}')
                continue
            
            self._creds[alias] = cred
        
        cursor.close()


    def set_module_creds(self, module, cred):
        '''Update module options based off the type of credential'''
        cred_type = self.get_cred_type(cred)
        opts = module._options
        
        if cred_type == Credential.CREDENTIAL_TYPE:
            pass
        
        elif cred_type == APICredential.CREDENTIAL_TYPE:
            pass

        elif cred_type == AWSCredential.CREDENTIAL_TYPE:
            opts.set_opt(AWSModule.OPT_ACCESS_KEY, cred._access_key_id)
            opts.set_opt(AWSModule.OPT_SECRET_KEY, cred._secret_key)
            opts.set_opt(AWSModule.OPT_SESSION_TOKEN, cred._session_token)
            opts.set_opt(AWSModule.OPT_AWS_REGION, cred._default_region)

        elif cred_type == 'MSFT':
            opts.set_opt(MicrosoftModule.OPT_AUTH_TOKEN, cred._access_token)
            opts.set_opt(MicrosoftModule.OPT_AUTH_PRINCIPAL, cred._principal)
            opts.set_opt(MicrosoftModule.OPT_AUTH_SECRET, cred._secret)
            opts.set_opt(MicrosoftModule.OPT_AUTH_TENANT, cred._tenant)
            pass

        elif cred_type == 'GCP':
            pass


    def get_cred_type(self, cred: CloudCredential) -> str:
        '''Return the string representation of the type of credential based of its class'''
        if isinstance(cred, GenericCredential):
            cred_type = 'Generic'
        elif isinstance(cred, APICredential):
            cred_type = 'API'
        elif isinstance(cred, AWSCredential):
            cred_type = 'AWS'
        elif isinstance(cred, MicrosoftCredential):
            cred_type = 'MSFT'
        elif isinstance(cred, GCPCredential):
            cred_type = 'GCP'
        else:
            self._framework.print_error(f'Unable to store unknown credential type: {cred_type}')
            cred_type = 'Unknown'

        return cred_type


    def store_credential(self, cred: Credential) -> bool:
        '''Save a CloudCredential object into the sqlite database'''
        cred_type = self.get_cred_type(cred)
        try:
            cursor = self._conn.cursor()
            query = f'INSERT INTO stratustryke VALUES (\"{cred._alias}\", \"{cred_type}\", \"{cred._workspace}\", \"{str(cred)}\")'
            cursor.execute(query)
            self._conn.commit()
            cursor.close()

            self._creds[cred._alias] = cred
            self._framework.print_status(f'Stored {cred_type} credential with alias: {cred._alias}')
            self._logger.info(f'Stored {cred_type} credential with alias: {cred._alias}')
        except Exception as err:
            self._framework.print_error(f'Exception thrown while storing credential: {cred._alias} - {err}')
            return False
        
        return True
        

    def remove_credential(self, alias: str) -> bool:
        try:
            cursor = self._conn.cursor()
            query = f'DELETE FROM stratustryke WHERE alias="{alias}"'
            cursor.execute(query)
            self._conn.commit()
            cursor.close()

            self._creds.pop(alias, None)
            self._framework.print_status(f'Removed credential: {alias}')
        except Exception as err:
            self._framework.print_error(f'Exception thrown while removing credential: {alias} - {err}')
            return False

        return True


    def list_aliases(self, workspace: str = None) -> list:
        '''Returns credential aliases for a given workspace.
        :return: list[str]'''
        if workspace == None:
            return [str(key) for key in self._creds.keys()]

        out = []
        for key in self._creds.keys():
            cred = self._creds[key]
            if cred._workspace == workspace:
                out.append(str(key))
        return out

    # # Todo: Query database and see if a credential entries exists with the supplied alias
    # def cred_alias_exists(self, alias: str) -> bool:
    #     return True

