# Author: @vexance
# Purpose: Base class definitions for AWS, Azure, and GCP class modules


import typing
import urllib3

from os import linesep
from http.client import responses as httpresponses
from requests import request, Response
from pathlib import Path

from stratustryke.core.option import Options
from stratustryke.core.framework import StratustrykeFramework
from stratustryke.lib import StratustrykeException


class StratustrykeModule(object):

    OPT_VERBOSE = 'VERBOSE'

    def __init__(self, framework: StratustrykeFramework) -> None:
        self.framework: StratustrykeFramework = framework
        self._info = { # set to false here to verify authors put this info in
            'Authors': False, # list[str} Authors who wrote the module
            'Details': False, # str detailed explanation of what the module does
            'Description': False, # str brief (one-line) summary of what module does
            'References': False # list[str] External references pertaining to the module
        }
        self._options = Options()
        self._options.add_boolean(StratustrykeModule.OPT_VERBOSE, 'When enabled, increases verbosity of module output', False, False)

        self._advanced = Options()

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


    @property
    def verbose(self) -> str:
        return self.get_opt(StratustrykeModule.OPT_VERBOSE)


    @property
    def desc(self) -> str:
        return self._info.get('Description', 'Unknown')

    @property
    def logger(self):
        return self.framework.get_module_logger(self.name)

    @property
    def path(self) -> str:
        return self.__module__.split('.', 3)[-1].replace('.', '/')

    @property
    def name(self) -> str:
        return self.path.split('/')[-1]

    @property
    def search_name(self) -> str:
        return f'generic/{self.name}'
    
    @property
    def web_proxies(self) -> dict:
        valid, msg = self.framework._config.get_opt(self.framework.CONF_HTTP_PROXY).validate()
        if not valid:
            raise StratustrykeException(msg)

        proxy = self.framework._config.get_val(self.framework.CONF_HTTP_PROXY)
        if proxy in ['', None]:
            return {}
        
        return {
            'http': proxy,
            'https': proxy
        }


    def show_options(self, mask: bool = False, truncate: bool = True) -> list:
        ''':return: list[list[str]] containing rows of column values'''
        return self._options.show_options(mask, truncate)


    def show_advanced(self, mask: bool = False, truncate: bool = True) -> list:
        ''':return: list[list[str]] containing rows of column values'''
        return self._advanced.show_options(mask, truncate)


    def validate_options(self) -> tuple:
        '''Validate option-specific requirements.\n
        :rtype: (bool, str | None)'''
        # Wrapper for Options class validate_options() call; can be overriden for additional checks
        base_opt_valid, msg = self._options.validate_options()
        if base_opt_valid:
            return self._advanced.validate_options()
        else:
            return base_opt_valid, msg


    def load_strings(self, file: str, is_paste: bool = False) -> list:
        '''
        Parse file lines from either a file (default) or pasted option value (when is_pasted = True).\n
        :param file: Path to the file OR raw pasted option value when is_paste = True
        :param is_paste: boolean flag indicating whether we're reading from file or parsing a string with line seperators
        :return: list[str] | None'''
        try:
            if not is_paste:
                file = Path(file)
                with open(file, 'r') as handle:
                    return [line.strip(f'{linesep}') for line in handle.readlines()]

            # Otherwise we're parsing a pasted option value which has \\n between each pasted line
            else: return file.split('\\n')
        
        except Exception as err:
            self.framework.print_error(f'Error reading contents of file: {file}')
            return None


    def get_opt_multiline(self, opt_name: str, **kwargs) -> list:
        '''
        Returns list[str] containing lines from an option file/paste or an individual value\n
        :param opt_name: (str) Option name to retrieve list value for
        :param delimiter: (str) Character to seperate value on if 'set' command was used
        :param unique: (bool) Flag which removes duplicate entries from the list (default: False)
        :return: list[str] parsed option string values
        '''
        delim = kwargs.get('delimiter', None)
        unique = kwargs.get('unique', False)
        value = self.get_opt(opt_name)

        if value == None or value == '':
            return None
        
        is_pasted = self._options.get_opt(opt_name)._pasted
        if is_pasted:
            parsed = self.load_strings(value, is_paste=True)
        elif Path.exists(Path(value)):
            parsed = self.load_strings(value, is_paste=False)
        else:
            if delim != None:
                parsed = value.split(delim)
            else: parsed = [value]

        if unique:
            if len(parsed) > 1:
                # Example duplicate removal if order should be preserved
                parsed = sorted(set(parsed), key=lambda idx: parsed.index(idx))
                # lines = list(set(lines)) # Otherwise, more simply if order does not matter
                parsed.remove('') # remove blank lines if necessary

        return parsed


    def http_request(self, method: str, url: str, **kwargs) -> Response:
        '''
        Wraps requests.request() while enforcing framework proxy / TLS verification configs\n
        :param method: (str) request method (e.g., GET, POST, PUT, etc)
        :param url: (str) URL for the request
        :param data: (str) non-json request body data
        :param json: (str) JSON request body data
        :param auth: (any) authentication. Support Sigv4
        '''
        proxies = kwargs.get('proxies', self.web_proxies)
        verify = kwargs.get('verify', self.framework._config.get_val(self.framework.CONF_HTTP_VERIFY_SSL))
        data = kwargs.get('data', None)
        auth = kwargs.get('auth', None)
        json = kwargs.get('json', None)
        headers = kwargs.get('headers', {})
        if self.framework._config.get_val(self.framework.CONF_HTTP_STSK_HEADER):
            headers.update({'X-Stratustryke-Module': f'{self.search_name}'})

        if method == 'GET': json, data = None, None # Ensure GET requests don't contain request body
        try:
            res = request(method, url, verify=verify, proxies=proxies, data=data, headers=headers, auth=auth, json=json)
            
            # res = request(method, url, verify=verify, proxies=proxies, params=params, data=data, headers=headers, cookies=cookies, auth=auth,
            #               files=files, timeout=timeout, allow_redirects=allow_redirects, hooks=hooks, stream=stream, cert=cert, json=json)
        except Exception as err:
            self.framework.print_error(f'Exception thrown ({type(err).__name__}) during HTTP/S request: {err}')
            self.framework._logger.error(f'Exception thrown ({type(err).__name__}) during HTTP/S request: {err}')
            return None
        
        return res


    def http_record(self, response: Response, outfile: str = None) -> list:
        '''Returns a list[str] containing raw HTTP request / response content. If ourfile is specified, will (over)write the lines to the file
        :param response: requests.Response object from a HTTP request
        :param outfile: string path to an output file to create. Overwrites if already existing.
        :return: list[str] containing raw HTTP request / response content'''
        lines = []
        request = response.request
        
        # Get raw request content
        url_path = request.url.split('/')[3:] # strip http: / / host /
        lines.append(f'{request.method} /{"".join(url_path)} HTTP/1.1{linesep}') # requests supports HTTP/1.1
        lines.extend([f'{key}: {request.headers[key]}{linesep}' for key in request.headers])
        lines.append(f'{linesep}')

        if request.body == None: lines.append(f'{linesep}')
        else: 
            if isinstance(request.body, bytes):
                request.body = request.body.decode()
            lines.append(f'{request.body}{linesep}')
        lines.append(f'{linesep}{linesep}')

        # Get raw response content
        status_description = httpresponses.get(response.status_code, 'UNKNOWN_STATUS_CODE')
        lines.append(f'HTTP/1.1 {response.status_code} {status_description}{linesep}')
        lines.extend([f'{key}: {response.headers[key]}{linesep}' for key in response.headers])
        lines.append(f'{linesep}')
        if response.text == None: lines.append(f'{linesep}')
        else: lines.append(f'{response.text}{linesep}')
        lines.append(f'{linesep}{linesep}')

        if outfile != None:
            self.framework._logger.info(f'Recording HTTP request/response to {outfile}')
            with open(outfile, 'w') as file:
                file.writelines(lines)

        return lines


    def show_info(self) -> list:
        '''Return module information and technical details. Should not be overriden in child classes\n
        :rtype: list<str> containing module information'''
        output = []
        output.append(f'  Module Name: {self.search_name}')
        output.append(f'  Author(s): {", ".join(self._info.get("Authors", []))}')
        
        output.append(f'  References:')
        for ref in self._info.get('References', []):
            output.append(f'  -  {ref}')
        
        output.append(f'  Description: {self.desc}')
        output.append(f'  Details:')
        output.append(f'    {self._info.get("Details", "UNKNOWN")}')

        return output


    def get_opt(self, name: str) -> typing.Any:
        '''Return the current value for the option; Pass to Options.get_val() NOTE: returns value, not the option object'''
        if name in self._options.keys():
            return self._options.get_val(name)
        elif name in self._advanced.keys():
            return self._advanced.get_val(name)
        else: return None # Not an option


    def set_opt(self, name: str, val: typing.Any) -> None:
        '''Sets the value for the option; Pass to Options.set_opt()'''
        if name in self._options.keys():
            self._options.set_opt(name, val)
        elif name in self._advanced.keys():
            self._options.set_opt(name, val)
        else: return None # Not a valid option


    def unset_opt(self, name: str) -> None:
        '''Sets value for the option to None; Pass to Options.unset_opt()'''
        if name in self._options.keys():
            self._options.unset_opt(name)
        elif name in self._advanced.keys():
            self._options.unset_opt(name)
        else: return None # Not a valid option


    def reset_opt(self, name: str) -> None:
        '''Reset value to default for the option; Pass to Options.reset_opt()'''
        if name in self._options.keys():
            self._options.reset_opt(name)
        elif name in self._advanced.keys():
            self._options.reset_opt(name)
        else: return None # Not a valid option


    ##### Framework output helpers #####

    def print_error(self, msg: str) -> None:
        '''Prints (magenta) error message: [x] {msg}'''
        return self.framework.print_error(msg)


    def print_status(self, msg: str) -> None:
        '''Prints (blue) status message: [*] {msg}'''
        return self.framework.print_status(msg)


    def print_warning(self, msg: str) -> None:
        '''Prints (yellow) warning message: [!] {msg}'''
        return self.framework.print_warning(msg)


    def print_success(self, msg: str) -> None:
        '''Prints (green) success message: [+] {msg}'''
        return self.framework.print_success(msg)
    

    def print_failure(self, msg: str) -> None:
        '''Prints (red) failure (not error!) message: [-] {msg}'''
        return self.framework.print_failure(msg)


    def print_line(self, msg: str) -> None:
        '''Prints line to the stdout with regular text: {msg}'''
        return self.framework.print_line(msg)


    def print_table(self, rows: list, headers: list, prefix: str = '  ', table_format: str = None):
        '''
        Prints a table to the framework
        :param rows: list[list[str]] list of rows containing a list of columns
        :param headers: list[str] containing column header names
        :param prefix: string to include before each line [default two spaces]
        :param table_format: type of table to generate'''
        return self.framework.print_table(rows, headers=headers, prefix=prefix, table_format=table_format)
    

    ##### Framework logging helpers #####
    def log_debug(self, msg: str) -> None:
        '''Log at DEBUG level'''
        return self.framework._logger.debug(f'[{self.search_name}] {msg}')


    def log_info(self, msg:str) -> None:
        '''Log at INFO level'''
        return self.framework._logger.info(f'[{self.search_name}] {msg}')


    def log_warning(self, msg:str) -> None:
        '''Log at WARN level'''
        return self.framework._logger.warning(f'[{self.search_name}] {msg}')


    def log_error(self, msg:str) -> None:
        '''Log at ERROR level'''
        return self.framework._logger.error(f'[{self.search_name}] {msg}')
    

    def log_critical(self, msg:str) -> None:
        '''Log at CRITICAL level'''
        return self.framework._logger.critical(f'[{self.search_name}] {msg}')



    #Must be implemented by inheriting classes
    def run(self) -> None:
      '''Execute current module. This essentially acts as the Module\'s main() function. This will automatically trigger option validation when set in the stratustryke config.'''
      pass

