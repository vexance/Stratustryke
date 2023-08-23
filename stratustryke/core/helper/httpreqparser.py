from pathlib import Path
import json
import re


class FileDoesNotExistException(Exception):
    '''Exception indicatiing that a specified file does not exist'''


class InvalidObjectTypeException(Exception):
    '''Class indicating that a passed argument is not valid for the associated parameter'''


class ChildMethodNotImplementedException(Exception):
    '''Class indicating that a required method has not been implemented by a child class of HTTPRequestParser'''


class InvalidHTTPBodyFormatException(Exception):
    '''Class indicating that the body within a HTTP request is not formatted properly for the parser type'''


class HTTPRequestParser(object):
    '''Class which will parse HTTP request files with JSON bodies and offer a means to create associated request objects'''
    def __init__(self, obj: object, hdrs: list = []) -> None:
        self.ignored_headers = hdrs
        if isinstance(obj, list): self.construct(None, lines=obj)
        elif isinstance(obj, str): self.construct(Path(obj), lines=None)
        elif isinstance(obj, Path): self.construct(obj, lines=None)
        else: raise InvalidObjectTypeException(type(obj))
        return None
        
    def construct(self, filepath: Path, lines: list = None) -> None:
        '''HTTPRequestParser constructor for file object types'''

        if filepath != None:
            exists = filepath.exists() and filepath.is_file()
            if not exists: raise FileDoesNotExistException(str(filepath))
        
        if lines == None:
            lines = []
            with open(filepath, 'r') as file:
                lines = [line.strip() for line in file.readlines()]

            self.api_name = filepath.stem

        else: self.api_name = None
        split = lines[0].split() # split on whitespace
        self.http_verb = split[0]
        self.http_path = split[1]
        self.http_version = split[2]
        self.http_headers = {}
        self.raw_body = ''
        self.protocol = None

        for i in range(1, len(lines)):
            if re.match('^Host:[\ ]+.*$', lines[i]): # Host header - save this for the full URL
                self.http_host = lines[i].split()[1]
            
            if re.match('^[a-zA-Z0-9\-]+[\:]{1}[\ ]+.*$', lines[i]): # is a non-Host header
                split = lines[i].split()
                header_name = split[0][0:-1] # remove the ':'
                header_value = split[1]

                if header_name in self.ignored_headers: continue

                self.http_headers[header_name] = header_value
            
            else: self.raw_body += f'{lines[i]}\n'

        self.raw_body = self.raw_body.strip()
        self.parse_body()
        return None


    def parse_body(self) -> None:
        '''Parses request body (must be overriden by child classes)'''
        raise ChildMethodNotImplementedException(f'{type(self).__name__}.parse_body()')
    

class HTTPJsonRequestParser(HTTPRequestParser):
    def __init__(self, obj: object, hdrs: list = []) -> None:
        super().__init__(obj, hdrs)

    def parse_body(self) -> None:
        '''Parses content specified within self.raw_body into a JSON dictionary'''
        if self.raw_body.strip() == '' or self.http_verb == 'GET':
            self.http_body=None
            return None

        try:
            self.http_body = json.loads(self.raw_body)
        except Exception as err:
            raise InvalidHTTPBodyFormatException(f'Invalid JSON detected:\n{self.raw_body}')
        
        return None            

