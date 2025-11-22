
from stratustryke.core.credential import CloudCredential
from stratustryke.settings import DEFAULT_WORKSPACE


AWS_ROLE_ARN_REGEX = '^arn:aws:iam::[0-9]{12}:role/.*$'
AZ_CLI_CLIENT_ID = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
AZ_MGMT_TOKEN_SCOPE = 'https://management.azure.com/.default'
M365_GRAPH_TOKEN_SCOPE = 'https://graph.microsoft.com/.default'
UUID_LOWERCASE_REGEX = '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'



class GCPCredential(CloudCredential):
    def __init__(self, alias: str, workspace: str = DEFAULT_WORKSPACE, verified: bool = False, 
        cred_id: str = None, acc_id: str = None, from_dict: dict = None):

        if from_dict != None:
            return super.__init__(alias, from_dict=from_dict)

        super().__init__(alias, workspace, verified, cred_id, acc_id)

    def __str__(self) -> str:
        return super().__str__()

