from stratustryke.core.module import AWSModule
from stratustryke.core.lib import StratustrykeException, module_data_dir
import stratustryke.core.command
import logging
from termcolor import colored
from pathlib import Path
import datetime
import requests
import os


class S3Object(object):
    def __init__(self, key: str, modified, size: int) -> None:
        self._key = key
        if isinstance(modified, datetime.datetime):
            self._modified = modified.strftime('%Y-%m-%d')
        else:
            self._modified = modified
        self._size = size

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)): return False
        return self._key == other._key

    def __hash__(self) -> int:
        return hash(self._key)

    @property
    def name(self) -> str:
        return self._key[self._key.rfind('/')+1:]

    @property
    def dir(self) -> str:
        return self._key[0:self._key.index(self.name)]

    @property
    def modified(self) -> str:
        return self._modified

    @property
    def size(self) -> str:
        if self._size > 1073741823: # gigabytes
            num = round(float(self._size / 1073741824), 2)
            return f'{num :<5} GB'
        elif self._size > 1048575: # megabytes
            num = round(float(self._size / 1048576), 2)
            return f'{num :<5} MB'
        elif self._size > 1023: # kilobytes
            num = round(float(self._size / 1024), 2)
            return f'{num :<5} KB'
        elif self._size < 0: # Used just to indicate a directory path
            return 'DIR     '
        else: # just bytes
            return f'{self._size :<6} B'


class S3Bucket():
    def __init__(self, name: str, create_time: datetime.datetime) -> None:
        self._name = name
        self._create_time = create_time.strftime('%Y-%m-%d %H:%M:%S')
        self._contents = set()

    @property
    def name(self) -> str:
        return self._name

    @property
    def create_time(self) -> str:
        return self._create_time

    @property
    def contents(self) -> list:
        return list(self._contents)

    @property
    def directories(self) -> list:
        ''':return: list[str]'''
        return list(set([obj.dir for obj in self.contents]))

    def add_obj(self, obj: S3Object):
        self._contents.add(obj)

    def dirs_in(self, search_dir: str) -> list:
        ''':return: list[S3Object]'''
        objects = set()
        directories = [obj for obj in self.directories if obj.startswith(search_dir)]
        for entry in directories:
            begidx = len(search_dir)
            endidx = entry.find('/', begidx+1)
            dir_name = entry[begidx:endidx]
            dir_obj = S3Object(f'/{dir_name}', 'XXXX-XX-XX', -1)
            objects.add(dir_obj)

        return sorted(list(objects), key = lambda obj: obj.name)

    def objects_in(self, search_dir: str) -> list:
        ''':return: list[S3Object]'''
        objects = set([obj for obj in self.contents if obj.dir == f'{search_dir}/'])
        return sorted(list(objects), key = lambda obj: obj.name)

    def ls_dir(self, search_dir: str) -> list:
        '''Return list of objects residing in a specified directory (prefix)
        :return: list[S3Object]'''
        # objects = set([obj for obj in self.contents if obj.dir == f'{search_dir}/'])
        # directories = [obj for obj in self.directories if obj.startswith(search_dir)]
        # for entry in directories:
        #     begidx = len(search_dir)
        #     endidx = entry.find('/', begidx+1)
        #     dir_name = entry[begidx:endidx]
        #     dir_obj = S3Object(f'/{dir_name}', 'XXXX-XX-XX', -1)
        #     objects.add(dir_obj)
        dirs = self.dirs_in(search_dir)
        objs = self.objects_in(search_dir)
        return dirs + objs
    
    def all_keys(self) -> list:
        ''':return: list[str]'''
        return [obj._key for obj in self.contents]



# helper functions #
def bucket_exists(framework, name: str) -> bool:
    try:
        url = f'http://{name}.s3.amazonaws.com'
        res = requests.get(url)

        if '<Code>NoSuchBucket</Code>' in res.text:
            framework.print_failure(f'S3 Bucket {name} does not exist')
            return False
            
        return True

    except Exception as err:
        framework.print_error(f'{err}')
        return False


class S3ClientExplorer(stratustryke.core.command.Command):
    def __init__(self, credential, stdin=None, stdout=None, framework=None, log_handler=None, bucket=None, download_dir=None, use_cache=False, **kwargs):
        super().__init__(stdin, stdout, **kwargs)
        self.cred = credential
        self.download_dir = download_dir
        self.framework = framework

        # Setup logging
        self.log_handler = log_handler
        if self.log_handler == None:
            self._hidden_commands.append('logging')
        self._logger = logging.getLogger('stratustryke.s3_client_explorer')

        # Print commands
        self.print_error = self.framework.print_error # magenta [x] msg
        self.print_status = self.framework.print_status # blue [*] msg
        self.print_warning = self.framework.print_warning # yellow [!] msg
        self.print_success = self.framework.print_success # green [+] msg
        self.print_failure = self.framework.print_failure # red [-] msg
        self.print_line = self.framework.print_line # regular text

        # Current bucket / prefix used for prompt & API calls
        self.use_cache = use_cache
        self.current_bucket = None if (bucket == '') else bucket
        self.current_prefix = ''
        self.discovered = {} # Format will be {'bucket_name': S3Bucket}
        self.current_dir_contents = []


    @property
    def intro(self) -> str:
        return f'{os.linesep}===<   Stratustryke S3 Client Explorer   >==={os.linesep}'

    @property
    def prompt(self) -> str:
        coloring = self.framework._config.get_val('COLORED_OUTPUT')
        prog_name = colored('stratustryke', 'blue', attrs=('bold',)) if (coloring) else stratustryke
        mod_name = colored('s3-explorer', 'green', attrs=('bold',)) if (coloring) else 's3-explorer'

        if self.current_bucket == None:
            return f'{prog_name} [{mod_name}] > '
        else: # there's bucket selected
            bucket = colored(f'{self.current_bucket}', 'yellow') if (coloring) else f'{self.current_bucket}'
            prefix = colored(f'/{self.current_prefix}', 'yellow') if (coloring) else f'/{self.current_prefix}'
            return f'{prog_name} [{mod_name}]({bucket}{prefix}) > '

    # === Utility === #

    def resolve_path(self, input_path: str) -> str:
        '''Take an input path and resolves it with the current prefix to build an absolute path'''
        current = '/' if self.current_prefix == '' else self.current_prefix
        current_path = Path(current)
        new_path = str((Path('/')/current_path/input_path).resolve())
        return new_path[1:] if (new_path[0] == '/') else new_path

    def is_discovered(self, bucket: str, key: str) -> bool:
        '''Returns whether an object has been discovered within the supplied bucket'''
        bucket = self.discovered[bucket]
        for directory in bucket.directories:
            if directory.startswith(f'{key}') or directory == key:
                return True
        for obj_key in self.discovered[bucket].all_keys():
            if obj_key == key:
                return True

        return False

    def get_discovered_objects(self, bucket: str, prefix: str = '/') -> list:
        ''':return: list[dict]'''
        objects = self.discovered.get(bucket, {}).get('Contents', [])
        return [obj for obj in objects if obj['Key'].startswith(prefix)]

    def get_download_dir(self) -> str:
        if self.current_bucket == None:
            return self.download_dir
        else:
            path = (Path(self.download_dir)/self.current_bucket).absolute()
            os.makedirs(path, exist_ok=True)
            return str(path)



    # ================================================ #
    #                S3 Client Commands                #
    # ================================================ #

    # Command: cache
    # Action: Shows or sets value for force api call setting
    # Syntax: 'cache', 'cache enable', 'cache disable'
    # Text Completion: enable, disable

    @stratustryke.core.command.command('Show, enable, or disable current setting for use of discovered object cache')
    @stratustryke.core.command.argument('value', nargs='?', choices=('enable', 'disable'), help = 'Enable or disable use of discovered object cache')
    def do_cache(self, args):
        if args.value == None:
            use_cached, avoid = 'enabled', '' if self.use_cache else 'disabled', 'not '
            self.framework.print_status(f'Use of discovered object cache is {use_cached}. Duplicate API calls will {avoid}be avoided.')

        elif args.value == 'enable':
            self.use_cache = True
            self.framework.print_status('Use of discovered object cache enabled. Avoiding duplicate API calls.')
        
        elif args.value == 'disable':
            self.use_cache = False
            self.framework.print_status('Use of discovered object cache disabled. Forcing API call upon command entry.')

    def complete_cache(self, text, line, begidx, endidx):
        return [i for i in ['enable', 'disable'] if i.startswith(text.lower())]

    # Command: 'clear'
    # Action: clears the terminal screen
    # Syntax: 'clear'
    # Aliases: 'cls'

    @stratustryke.core.command.command('Clear terminal screen')
    def do_clear(self, args):
        if stratustryke.settings.on_linux:
            os.system('clear')
        elif stratustryke.settings.on_windows:
            os.system('cls')
        else:
            self.print_line('Unknown system OS is not Linux or Windows')

    def do_cls(self, args):
        '''Alias for command 'clear' '''
        self.do_clear(args)

    # Command: buckets
    # Action: Performs s3:ListBuckets call to view buckets listable by the credentialed user
    # Syntax: 'buckets'

    @stratustryke.core.command.command('List s3 buckets visible to the user with s3:ListBuckets')
    def do_buckets(self, args):
        # If forcing re-calling APIs or if there is nothing discovered
        if self.use_cache == False or self.discovered == {}:
            session = self.cred.session()
            client = session.client('s3')

            try:
                res = client.list_buckets()
                buckets = res.get('Buckets', [])

                for entry in buckets:
                    name = entry.get('Name', 'Unknown')
                    creation_date = entry.get('CreationDate', None)
                    if name not in self.discovered.keys():
                        self.discovered[name] = S3Bucket(name, creation_date)

            except Exception as err:
                self.framework.print_failure(f'{err}')
                return

        # No buckets found
        if len(self.discovered.keys()) < 1:
            self.framework.print_line('No buckets found')
            return

        # Print buckets along with their creation timestamp
        for name in self.discovered.keys():
            bucket = self.discovered.get(name)
            self.framework.print_line(f'{bucket.create_time :<12}   {bucket.name}')

        self.framework.print_line('')

    # Command: use
    # Action: Select an s3 bucket as the current bucket
    # Syntax: 'use <bucket>'
    # Text Completion: discovered buckets
    
    @stratustryke.core.command.command('Select an s3 bucket as the current bucket')
    @stratustryke.core.command.argument('bucket', help = 'Bucket to explore')
    def do_use(self, args):
        if args.bucket not in self.discovered.keys():
            exists = bucket_exists(self.framework, args.bucket)
            if not exists:
                return

        self.current_bucket = args.bucket
        self.current_prefix = ''
            
    def complete_use(self, text, line, begidx, endidx):
        return[str(key) for key in self.discovered.keys() if str(key).startswith(text.lower())]


    # Command: back
    # Action: deselects the current bucket and resets prefix
    # Syntax: 'back'

    @stratustryke.core.command.command('Deselect the current bucket')
    def do_back(self, args):
        self.current_bucket = None
        self.current_prefix = ''


    # Command: ls
    # Action: Lists bucket objects with the current prefix up to the next '/'; adds these to discovered items
    # Syntax: 'ls', 'ls <path>'
    # Text Completion: discovered objects ending with '/'

    @stratustryke.core.command.command('List bucket objects with the current directory key prefix wtih s3:ListObjects')
    @stratustryke.core.command.argument('path', nargs='?', help = 'Path to directory key prefix to list contents of [\'.\' if not specified]')
    def do_ls(self, args):
        if self.current_bucket == None:
            self.framework.print_line('No bucket selected')
            return

        if args.path == None:
            path = self.current_prefix
        else:
            path = self.resolve_path(args.path)

        results = self.discovered[self.current_bucket].ls_dir(path)
        if len(results) < 1 or (not self.use_cache): # no results found OR not using cache
            self.list_bucket(path)
            results = self.discovered[self.current_bucket].ls_dir(path)

        for obj in results:
                if obj.name == '':
                    continue # skip empty name entries
                self.framework.print_line(f'{obj.modified :<12} {obj.size :<10}{obj.name}')
        self.framework.print_line('')
        return

    def list_bucket(self, prefix: str = ''):
        # List bucket objects
        try:
            session = self.cred.session()
            client = session.client('s3')

            # Get first page
            res = client.list_objects_v2(Bucket=self.current_bucket,Prefix=prefix)
            paginating, token, entries = self.parse_list_object_response(res)
            # Continue paginating as necessary
            while paginating:
                res = client.list_objects_v2(Bucket=self.current_bucket,ContinuationToken=token,Prefix=prefix)
                paginating, token, results = self.parse_list_object_response(res)
                entries.extend(results)

            # Add all objects to the current bucket
            for object in entries:
                self.discovered[self.current_bucket].add_obj(object)

        except KeyboardInterrupt:
            self.print_status('Received keyboard interrupt while paginating s3:ListObjects')
        except Exception as err:
            self.framework.print_failure(f'{err}')
            return

    def parse_list_object_response(self, res: dict) -> tuple:
        '''Returns (bool, str|None, list[dict]) where bool indicates where pagination needs to continue'''
        paginating = res.get('IsTruncated', False) # whether we need to paginate resonses
        results = []

        for object in res.get('Contents', []):
            key = object.get('Key', False)
            modified  = object.get('LastModified', False)
            size = object.get('Size', False)
            
            self._logger.info(f'Found s3 object via s3:ListObjects: {key}')
            if not (key and modified and size > -1):
                continue # invalid response item
            
            s3_obj = S3Object(key, modified, size)
            results.append(s3_obj)

        token = res.get('NextContinuationToken', None)
        return paginating, token, results


    # Command: cd
    # Action: Update key prefix, abstracting the directory location
    # Syntax: 'cd', 'cd <path>'
    # Text Completion: Discovered s3 objects ending with '/'

    @stratustryke.core.command.command('Change the current directory key prefix')
    @stratustryke.core.command.argument('path', nargs='?', help = 'Path to new directory. If unspecified, returns to bucket root')
    def do_cd(self, args):
        if self.current_bucket == None:
            self.framework.print_line('No bucket selected')
            return

        if args.path == None:
            self.current_prefix = ''
            return

        resolved = self.resolve_path(args.path)
        if resolved == '':
            self.current_prefix = ''
            return

        if self.is_discovered(self.current_bucket, f'{resolved}/'):
            self.current_prefix = resolved
        else:
            self.framework.print_line(f'Path {resolved} has not been discovered yet.')
            return

    def complete_cd(self, text, line, begidx, endidx):
        objs = self.discovered[self.current_bucket].dirs_in(self.current_prefix) + [S3Object('/..', 'XXXX-XX-XX', -1)]
        return [f'{obj.name}/' for obj in objs if obj.name.startswith(text)]


    # Command: get
    # Action: Attempts to perform s3:GetObject on the specified object
    # Syntax: 'get <path>'
    # Text Completion: files within the current directory

    @stratustryke.core.command.command('Attempt to retrieve object with s3:GetObject')
    @stratustryke.core.command.argument('path', help = 'Path to object from the current directory')
    def do_get(self, args):
        if self.current_bucket == None:
            self.framework.print_line('No bucket selected')
            return
        
        obj_key = self.resolve_path(args.path)

        try:
            session = self.cred.session()
            client = session.client('s3')

            res = client.get_object(Bucket=self.current_bucket, Key=obj_key)
            body = res.get('Body', None)
            if body == None:
                raise StratustrykeException(f'Unable to retrieve s3://{self.current_bucket}/{obj_key}')

            obj_bytes = body.read()
            download_dir = self.get_download_dir()
            filename = obj_key[obj_key.rfind('/')+1:]

            with open((Path(download_dir)/filename), 'wb') as file:
                file.write(obj_bytes)

            self.framework.print_success(f'Downloaded {filename} to {download_dir}')

        except Exception as err:
            self.framework.print_failure(f'{err}{os.linesep}')
            self.framework._logger.error(f'{err}')
            return

    def complete_get(self, text, line, begidx, endidx):
        objs = self.discovered[self.current_bucket].objects_in(self.current_prefix)
        return [obj.name for obj in objs if obj.name.startswith(text)]



class Module(AWSModule):

    OPT_BUCKET_NAME = 'BUCKET_NAME'
    OPT_USE_CACHE = 'USE_CACHE'
    OPT_DOWNLOAD_DIR = 'DOWNLOAD_DIR'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'S3 interactive explorer with ftp-like syntax and output',
            'Details': 'Launches an interactice interpreter which parses ftp style commands and wraps them into S3 API calls. Formats output from the API calls to provide an ftp client look and feel. Permissions used by this module include s3:ListBuckets, s3:ListAllMyBuckets, s3:ListObjects, s3:GetObject, s3:PutObject, s3:GetObjectTagging, s3:HeadBucket, s3:HeadObject',
            'References': ['']
        }
        self._options.add_string(Module.OPT_BUCKET_NAME, 'Name of s3 bucket to use as the explorer startup bucket', False)
        self._options.add_boolean(Module.OPT_USE_CACHE, 'Enables use of \'discovered object cache\' which avoids duplicate API calls', True, True)
        self._options.add_string(Module.OPT_DOWNLOAD_DIR, 'Directory files will be downloaded to', True, module_data_dir(self.name))

    @property
    def search_name(self):
        return f'aws/s3/util/{self.name}'


    def validate_options(self) -> tuple:
        valid, msg = super().validate_options()
        if not valid:
            return (False, msg)

        download_dir = self.get_opt(Module.OPT_DOWNLOAD_DIR)
        download_dir = Path(download_dir).resolve().absolute()
        if not (download_dir.exists() and download_dir.is_dir()):
            return (False, f'Download directory does not exist: {download_dir}')

        return (True, None)


    def run(self):
        cred = self.get_cred()
        bucket = self.get_opt(Module.OPT_BUCKET_NAME)
        use_cache = self.get_opt(Module.OPT_USE_CACHE)
        download_dir = self.get_opt(Module.OPT_DOWNLOAD_DIR)
        download_dir = str(Path(download_dir).resolve().absolute())


        if not (bucket == None or bucket == ''):
            exists = self.bucket_exists(self.framework, bucket)
            if not exists:
                return False

        self.framework.print_status(f'Launching s3-explorer client (Download directory: {download_dir})')
        interpreter = S3ClientExplorer(cred, framework=self.framework, bucket=bucket, use_cache=use_cache, download_dir=download_dir)
        interpreter.cmdloop()
        return True
