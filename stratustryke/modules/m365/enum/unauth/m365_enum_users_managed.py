from stratustryke.core.module import StratustrykeModule
import re
import string
import random
import requests

class Module(StratustrykeModule):

    OPT_USERNAME = 'USERNAME'
    OPT_DOMAIN = 'DOMAIN'
    OPT_FIREPROX_URL = 'FIREPROX_URL'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Enumerate valid email addresses in a manged Microsoft 365 domain',
            'Details': 'Performs enumeration of email addresses after checking that the specifed logon domain is a mangaed Microsoft 365 tenant. Derived from \'o365enum\' which was contributed to by @jenic, @gremwell, @BarrelTi0r, and @vexance. This module supports designation of a fireprox proxy. This proxy can be created with the command \'fireprox create https://login.microsoftonline.com/common/GetCredentialType?mkt=en-US\' when the necessary credential object is stored in the Stratustryke CredStore.',
            'References': ['https://github.com/vexance/o365enum']
        }

        self._options.add_string(Module.OPT_USERNAME, 'Username(s) / email addresses to enumerate (F/P)', True)
        self._options.add_string(Module.OPT_DOMAIN, 'Microsoft 365 (managed) domain to enumerate users within (F/P)', False)
        
        self._advanced.add_string(Module.OPT_FIREPROX_URL, 'Fireprox URL [https://login.microsoftonline.com/common/GetCredentialType?mkt=en-US] (Reccommended for 100+ users)', False)


    @property
    def search_name(self) -> str:
        return f'm365/enum/unauth/{self.name}'
    

    def format_usernames(self) -> str:
        usernames = self.lines_from_string_opt(Module.OPT_USERNAME, unique=True)

        usernames = list(set(usernames))
        domains = self.lines_from_string_opt(Module.OPT_DOMAIN, unique=True)

        if domains == None:
            self.print_status('No M365 domain specified; only email addresses set in option USERNAME will be enumerated')

        addresses = []
        for user in usernames:
            user_has_domain_suffix = '@' in user
            
            if user_has_domain_suffix: # 'user@domain.tld', do not append a domain
                addresses.append(user)
            else: # just 'user
                if domains == None:
                    self.print_warning(f'Skipping \'{user}\' because no domain(s) specified')
                    continue

                addresses.extend([f'{user}@{domain}' for domain in domains])
        
        return addresses
                

    def apply_stsk_header(self, headers: dict) -> dict:
        '''Adds X-Stratustryke-Module header if necessary per HTTP_STSK_HEADER config option'''
        if self.framework._config.get_val(self.framework.CONF_HTTP_STSK_HEADER):
            headers.update({'X-Stratustryke-Module': f'{self.search_name}'})

        return headers


    def run(self) -> None:

        fp_url = self.get_opt(Module.OPT_FIREPROX_URL)
        if fp_url == None or fp_url == '':
            endpoint = 'https://login.microsoftonline.com/common/GetCredentialType?mkt=en-US'
        else: endpoint = fp_url
        proxies = self.web_proxies
        addresses = self.format_usernames()
        # Prep session headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36'
        }
        headers = self.apply_stsk_header(headers)

        # Simulate opening of M365 main page
        session = requests.session()
        response = session.get('https://www.office.com', headers=headers, proxies=proxies)

        # Obtain application and session identifiers
        client_id = re.findall(b'"appId":"([^"]*)"', response.content)

        # Request /login in order to redirect to the authenitcation workflow
        response = session.get('https://www.office.com/login?es=Click&ru=/&msafed=0', headers=headers, allow_redirects=True, proxies=proxies)
        hpgid = re.findall(b'hpgid":([0-9]+),', response.content)
        hpgact = re.findall(b'hpgact":([0-9]+),', response.content)

        if not all([client_id, hpgid, hpgact]):
            raise Exception('An error occured when generating headers.')

        # Apply appropriate headers that M365 expects in order make traffic appear more normal
        headers['client-request-id'] = client_id[0]
        headers['Referer'] = response.url
        headers['hpgrequestid'] = response.headers['x-ms-request-id']
        headers['canary'] = ''.join(
            random.choice(
                string.ascii_uppercase + string.ascii_lowercase + string.digits + '-_'
            ) for i in range(248)
        )
        headers['hpgid'] = hpgid[0]
        headers['Accept'] = 'application/json'
        headers['hpgact'] = hpgact[0]
        headers['Origin'] = 'https://login.microsoftonline.com'

        # Base JSON request body
        payload = {
            'isOtherIdpSupported':True,
            'checkPhones':False,
            'isRemoteNGCSupported':True,
            'isCookieBannerShown':False,
            'isFidoSupported':False,
            'originalRequest': re.findall(b'"sCtx":"([^"]*)"', response.content)[0].decode('utf-8'),
            'forceotclogin':False,
            'isExternalFederationDisallowed':False,
            'isRemoteConnectSupported':False,
            'federationFlags':0,
            'isSignup':False,
            'isAccessPassSupported':True
        }

        # Result codes indicating user / address status
        ifExistsResultCodes = {
            '-1': 'UNKNOWN',
            '0': 'VALID_USER',
            '1': 'INVALID_USER',
            '2': 'THROTTLE',
            '4': 'ERROR',
            '5': 'VALID_USER_DIFFERENT_IDP',
            '6': 'VALID_USER'
        }

        # Domain type ids from the resposne
        domainType = {
            "1": "UNKNOWN",
            "2": "COMMERCIAL",
            "3": "MANAGED",
            "4": "FEDERATED",
            "5": "CLOUD_FEDERATED"
        }

        environments = dict()

        # Iterate through usernames
        for email in addresses:
            # Check to see if this domain has already been checked
            # If it's managed, it's good to go and we can proceed
            # If it's anything else, don't bother checking
            # If it hasn't been checked yet, look up that user and get the domain info back
            domain_idx = email.rfind('@')+1
            domain = email[domain_idx:] if ('@' in email) else ''

            if not domain in environments or environments[domain] == "MANAGED":
                payload["username"] = email
                response = session.post(endpoint, headers=headers, json=payload, proxies=proxies)
                if response.status_code == 200:
                    throttleStatus = int(response.json()['ThrottleStatus'])
                    ifExistsResult = str(response.json()['IfExistsResult'])
                    environments[domain] = domainType[str(response.json()['EstsProperties']['DomainType'])]

                    if environments[domain] == "MANAGED":
                        # NotThrottled:0,AadThrottled:1,MsaThrottled:2
                        if not throttleStatus == 0:
                            self.print_warning(f'{email} - Possible throttle detected on request')
                        if ifExistsResult in ['0', '6']: #Valid user found!
                            self.print_success(f'{email} - Valid user')
                        elif ifExistsResult == '5': # Different identity provider, but still a valid email address
                            self.print_status(f'{email} - Valid user with different IDP')
                        elif ifExistsResult == '1':
                            self.print_failure(f'{email} - Invalid user')
                        else:                    
                            self.print_warning(f'{email} - {ifExistsResultCodes[ifExistsResult]}')
                    else:
                        self.print_warning(f'{email} - Domain type \'{environments[domain]}\' not supported')
                else:
                    self.print_warning(f'{email} - Request error')
            else:
                self.print_warning(f'{email} - Domain type \'{environments[domain]}\' not supported')

