from pathlib import Path
from copy import deepcopy
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


class DictionaryMutationException(Exception):
    '''Class indicating an exception was thrown while mutating JSON request body'''


class StratustrykeDictionaryParser(object):
    def __init__(self, dictionary: dict) -> None:
        self.original = dictionary
        self.mapped_items = {}
        self.extract_items(dictionary, '')

    @property
    def items(self):
        return self.mapped_items

    def extract_items(self, obj, currentkey: str) -> None:
        '''Recursively maps key:value pairs within an objects items'''
        if isinstance(obj, dict):
            for key, value in obj.items():
                self.extract_items(value, f'{currentkey}.{key}')
        
        elif isinstance(obj, list):
            for listitem in obj:
                idx = obj.index(listitem)
                self.extract_items(listitem, f'{currentkey}.[{idx}]')
            
        else:
            fullkey = currentkey[1:] if currentkey.startswith('.') else currentkey
            self.mapped_items[fullkey] = obj


    def update_value(self, obj, param_path: str, regex, start, end, value) -> int:
        ''''''
        keysplit = param_path.split('.')
        key = keysplit[0]

        if re.match('\[[0-9]+\]', key):
            key = int(key[1:-1]) # list index; remove brackets & cat to int

        if len(keysplit) == 1: # stop traversing, update value
            current = obj[key]
            before = current[0:start]
            after = current[end:]
            obj[key] = f'{before}{value}{after}'
            return f'{current[start:end]} => {value}'
        
        else: return self.update_value(obj[key], '.'.join(keysplit[1:]), regex, start, end, value)
            


    def mutate(self, regex: str, replacement: str) -> dict:
        key_matches = []

        # First, determine which values match the pattern
        for key, value in self.mapped_items.items():
            if not isinstance(value, str): continue
            indeces = [(m.start(), m.end()) for m in re.finditer(regex, value)]
            for start, end in indeces:
                key_matches.append((key, start, end))
        

        # Now, we'll have to determine the depth of the deepest value
        mutations = []
        for key, start, end in key_matches:
            copy = deepcopy(self.original)
            self.update_value(copy, key, regex, start, end, replacement)
            mutations.append(copy)

        return mutations



    def generate_mutations(self, regex: str, replacements: list) -> list:
        mutations = []
        for entry in replacements:
            mutations.extend(self.mutate(regex, entry))

        return mutations
    

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
    
    def generate_mutations(self, regex: str, replacements: list) -> None:
        '''Mutates request body by replacing matches to the regex with supplied replacement values'''
        raise ChildMethodNotImplementedException(f'{type(self).__name__}.generate_mutations()')


class HTTPJsonRequestParser(HTTPRequestParser):
    def __init__(self, obj: object, hdrs: list = []) -> None:
        super().__init__(obj, hdrs)

    def generate_mutations(self, regex: str, replacements: list) -> list:
        '''
        Mutates the request HTTP body by replacing regex matches with values in the provided list.
        :param regex: (str) regex pattern to match request string values on
        :param replacements: list[str] list of values to inject into each matched location
        :return: list[dict] containing the mutated request bodies
        '''

        try:
            parser = StratustrykeDictionaryParser(self.http_body)
            return parser.generate_mutations(regex, replacements)
        except Exception as err:
            raise DictionaryMutationException(f'Exception thrown while mutating request body: {err}\n{self.http_body}')
        

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
