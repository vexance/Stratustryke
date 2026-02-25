
from stratustryke.core.credential import CloudCredential
from stratustryke.settings import DEFAULT_WORKSPACE


class GCPCredential(CloudCredential):

    CREDENTIAL_TYPE = 'GCP'

    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verified: bool = False, 
        cred_id: str = None, acc_id: str = None, from_dict: dict = None):

        if from_dict != None:
            return super.__init__(alias, from_dict=from_dict)

        super().__init__(alias, workspace, verified, cred_id, acc_id)

    def __str__(self) -> str:
        return super().__str__()

