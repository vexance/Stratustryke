

from stratustryke.core.module.azure import AzureModule, AZ_MGMT_REST_URL
from stratustryke.core.credential.microsoft import AZ_MGMT_TOKEN_SCOPE
from stratustryke.lib import module_data_dir

class Module(AzureModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        # self._info = {
        #     'Authors': ['@vexance'],
        #     'Description': 'Exfiltrate values for string type deployment parameters',
        #     'Details': 'Retrieves String type deployment parameters for resource group & subscription deployments',
        #     'References': [ 'https://github.com/vexance/RunbookExporter' ]
        # }

        # self._options.add_string('ACCOUNT_PREFIX', 'Prefix for automation accounts to inclde (default: ALL) [S/F/P]')
        # self._options.add_string('RUNBOOK_PREFIX', 'Prefix for runbooks to include (default: ALL) [S/F/P]', False)
        
        self.auth_token = None

    
    @property
    def search_name(self):
        return f'azure/functionapp/enum/{self.name}'
    

    def list_function_apps(self, subscription: str) -> list[str]:
        '''Return list[str] containing resource id paths for function apps in the subscription'''

        token = self.get_cred().access_token(AZ_MGMT_TOKEN_SCOPE)
        path = f"subscriptions/{subscription}/providers/Microsoft.Web/sites?api-version=2025-03-01"
        headers = {'Authorization': f'Bearer {token}'}

        res = self.http_request('GET', f'{AZ_MGMT_URL}/{path}', headers=token)

        if not res.ok:
            self.print_error(f'Error during GET /{path}')
            if self.verbose: self.print_error(f'{res.status_code} {res.text}')
            return
        
        else: data = res.json()

        function_apps = []
        for app in data.get("value", []):
            kind = (app.get("kind") or "").lower()
            if "functionapp" in kind:
                function_apps.append(app)

        # Handle pagination if necessary
        next_link = data.get("nextLink")
        while next_link:
            resp = self.http_request("GET", next_link, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            for app in data.get("value", []):
                kind = (app.get("kind") or "").lower()
                if "functionapp" in kind:
                    function_apps.append(app)
            next_link = data.get("nextLink")

        return function_apps
    

    def parse_rg_and_name(self, app: dict) -> tuple:
        '''Parse resource group + app name from the `id` of a Microsoft.Web/sites resource.'''
        rid = app["id"]
        parts = rid.split("/")
        # Example: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{name}
        rg_idx = parts.index("resourceGroups") + 1
        name_idx = parts.index("sites") + 1
        rg = parts[rg_idx]
        name = parts[name_idx]
        return rg, name


    def list_functions_for_app(self, subscription: str, app: dict):
        '''List functions inside a Function App using Web Apps - List Functions.'''
        rg, name = self.parse_rg_and_name(app)
        token = self.get_cred().access_token(AZ_MGMT_TOKEN_SCOPE)
        headers = {'Authorization': f'Bearer {token}'}
        path = f'subscriptions/{subscription}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{name}/functions?api-version=2025-03-1'

        try:
            res = self.http_request('GET', f'{AZ_MGMT_URL}/{path}', headers=headers)
        except RuntimeError as e:
            self.print_warning(f'Failed to list functions for {name}')
            if self.verbose: self.print_error(str(e))
            return []

        return res.json().get("value", [])


    def run(self) -> None:
        self.auth_token = self.get_cred().access_token(scope=AZ_MGMT_TOKEN_SCOPE)
        subscriptions = self.get_opt_az_subscription()