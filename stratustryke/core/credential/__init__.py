
from ast import literal_eval

from stratustryke.settings import DEFAULT_WORKSPACE


class Credential:

    CREDENTIAL_TYPE = 'Generic'

    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verfied: bool = False, from_dict: str = None):
        if from_dict != None:
            from_dict = literal_eval(from_dict)
            for key in from_dict.keys():
                attr = str(key)
                self.__setattr__(attr, from_dict.get(key))
            return
        else:
            self._alias = alias
            self._workspace = workspace
            self._verified = verfied


    def __str__(self) -> str:
        builder = {}
        builder['_alias'] = self._alias
        builder['_verified'] = self._verified
        builder['_workspace'] = self._workspace
        return str(builder)

    
    def to_string(self) -> str:
        return self.__str__()


class GenericCredential(Credential):
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verfied: bool = False, secret_name: str = None, secret_value: str = None, from_dict: dict = None):
        if from_dict != None:
            return super().__init__(alias, from_dict=from_dict)
        else:
            super().__init__(alias, workspace, verfied)
            self._secretname = secret_name
            self._secretvalue = secret_value


    def __str__(self) -> str:
        tmp = super().__str__()
        builder = literal_eval(tmp)
        builder['_secretname'] = self._secretname
        builder['_secretvalue'] = self._secretvalue
        return str(builder)


class APICredential(Credential):

    CREDENTIAL_TYPE = 'API'

    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verfied: bool = False, auth_type: str = None, secret: str = None, endpoint: str = None, from_dict: dict = None):
        if from_dict != None:
            return super().__init__(alias, from_dict=from_dict)
        else:
            super().__init__(alias, workspace, verfied)
            self._auth_type = auth_type # Key, Authorization: Bearer, etc
            self._secret = secret
            self._endpoint = endpoint

    def __str__(self) -> str:
        tmp = super().__str__()
        builder = literal_eval(tmp)
        builder['_auth_type'] = self._auth_type
        builder['_secret'] = self._secret
        builder['_endpoint'] = self._endpoint
        return str(builder)


class CloudCredential(Credential):
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verfied: bool = False, acc_id: str = None, cred_id: str = None, from_dict: dict = None):
        if from_dict != None:
            return super().__init__(alias, from_dict=from_dict)
        else:
            super().__init__(alias, workspace, verfied)
            self._account_id = acc_id
            self._cred_id = cred_id

    def __str__(self) -> str:
        tmp = super().__str__()
        builder = literal_eval(tmp)
        builder['_account_id'] = self._account_id
        builder['_cred_id'] = self._cred_id
        return str(builder)
