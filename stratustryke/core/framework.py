# Author: @vexance
# Purpose: Stratustryke frameowrk - handles module management, user configs, and I/O
#

import importlib
import logging
import logging.handlers
import pathlib
import sys
import tabulate
import os

from termcolor import colored

from stratustryke.core.credstore import CredentialStoreConnector
from stratustryke.core.module import StratustrykeModule
from stratustryke.core.option import Options
from stratustryke.core.fireprox import FireProx
from stratustryke.core.modmgr import ModManager
from stratustryke import lib, settings


class StratustrykeFramework(object):
    '''
    Main instance of the framework which handles configurations, loaded modules, passes input between CLI and modules, and handles terminal / file output
    '''

    CONF_MASK_SENSITIVE = 'MASK_SENSITIVE'
    CONF_COLORED_OUTPUT = 'COLORED_OUTPUT'
    CONF_FORCE_VALIDATE_OPTIONS = 'FORCE_VALIDATE_OPTIONS'
    CONF_SPOOL_OVERWRITE = 'SPOOL_OVERWRITE'
    CONF_TRUNCATE_OPTIONS = 'TRUNCATE_OPTIONS'
    CONF_FIREPROX_CRED_ALIAS = 'FIREPROX_CRED_ALIAS'
    CONF_DEFAULT_TABLE_FORMAT = 'DEFAULT_TABLE_FORMAT'
    CONF_WORKSPACE = 'WORKSPACE'
    CONF_HTTP_PROXY = 'HTTP_PROXY'
    CONF_HTTP_VERIFY_SSL = 'HTTP_VERIFY_SSL'
    CONF_HTTP_STSK_HEADER = 'HTTP_STSK_HEADER'

    def __init__(self, stdout = None):
        # Package info
        self.__package__ = '.'.join(self.__module__.split('.')[:-1])
        package_path = importlib.import_module(self.__package__).__path__[0]  # honestly no idea how / if this works

        # stdout and install / user data dirs
        self._stdout = sys.stdout if (stdout == None) else stdout
        self._user_data_dir = lib.home_dir()
        self._install_dir = lib.stratustryke_dir()

        # Logging setup
        self._logger = logging.getLogger('stratustryke.framework')
        tmp_path = str(pathlib.Path(self._user_data_dir/self.__package__).absolute())
        os.makedirs(tmp_path, exist_ok=True)

        raw_loglevel = settings.STRATUSTRYKE_LOGLEVEL
        loglevel = logging.INFO # Default to info if not designated in settings (or invalid val in settings)
        if raw_loglevel == 'DEBUG':  loglevel = logging.DEBUG
        elif raw_loglevel == 'INFO': loglevel = logging.INFO
        elif raw_loglevel == 'WARNING': loglevel = logging.WARNING
        elif raw_loglevel == 'ERROR': loglevel = logging.ERROR
        elif raw_loglevel == 'CRITICAL': loglevel = logging.CRITICAL

        logging_file_handle = logging.handlers.RotatingFileHandler(pathlib.Path(self._user_data_dir/self.__package__/'stratustryke.log').absolute(), maxBytes=262144, backupCount=5)
        logging_file_handle.setLevel(loglevel)
        logging_file_handle.setFormatter(logging.Formatter("%(asctime)s %(name)-50s %(levelname)-10s %(message)s"))
        logging.getLogger('').addHandler(logging_file_handle)

        # Framework options
        self._config = Options()
        self._config.add_boolean(StratustrykeFramework.CONF_MASK_SENSITIVE, 'Configure masking of sensitive option values in module options display', True, settings.MASK_SENSITIVE_OPTIONS)
        self._config.add_boolean(StratustrykeFramework.CONF_COLORED_OUTPUT, 'Enables color in console output', True, settings.COLORED_OUTPUT)
        self._config.add_boolean(StratustrykeFramework.CONF_FORCE_VALIDATE_OPTIONS, 'Enables validation checks on module options upon running the module', True, settings.FORCE_VALIDATE_OPTIONS)
        self._config.add_boolean(StratustrykeFramework.CONF_SPOOL_OVERWRITE, 'Enables spool file overwrite and disables default writing mode (append) for file spooling ops', True, settings.SPOOL_OVERWRITE)
        self._config.add_boolean(StratustrykeFramework.CONF_TRUNCATE_OPTIONS, 'Enables / disables truncation of long option values to avoid line-breaks in terminal', True, settings.TRUNCATE_OPTIONS)
        self._config.add_string(StratustrykeFramework.CONF_FIREPROX_CRED_ALIAS, 'Credential alias to use for management of fireprox APIs', True, settings.FIREPROX_CRED_ALIAS)
        self._config.add_string(StratustrykeFramework.CONF_DEFAULT_TABLE_FORMAT, 'Default outputing format for table output', True, settings.DEFAULT_TABLE_FORMAT)
        self._config.add_string(StratustrykeFramework.CONF_WORKSPACE, 'Workspace to filter credential objects in the stratustryke sqlite credstore', True, settings.DEFAULT_WORKSPACE)
        self._config.add_string(StratustrykeFramework.CONF_HTTP_PROXY, 'Proxy (schema://host:port) for modules to use as an HTTP/S proxy for web traffic', False, None, '(http[s]?|socks[45][h]?)[:]\\/\\/.*[:][0-9]{1,5}')
        self._config.add_boolean(StratustrykeFramework.CONF_HTTP_VERIFY_SSL, 'Enable or disable SSL/TLS verification when modules perform manual HTTP requests', True, settings.HTTP_VERIFY_SSL)
        self._config.add_boolean(StratustrykeFramework.CONF_HTTP_STSK_HEADER, 'Enable / disable submission of X-Stratustryke-Header for custom HTTP requests', True, settings.HTTP_STSK_HEADER)

        # Load modules into framework - get modules dir and all directories below it
        self.current_module = None

        search_dirs = []
        builtin_modules_dir = (lib.stratustryke_dir()/'modules').absolute()
        for directory in builtin_modules_dir.glob('**/'):
            path = str(directory)
            if not path.endswith('__pycache__'):
                search_dirs.append(path)

        self.spooler = None # Will hold the I/O handle
        self.spool_mode = None
        self.credentials = CredentialStoreConnector(self, str(lib.sqlite_filepath()))
        
        fp_alias = self._config.get_opt(StratustrykeFramework.CONF_FIREPROX_CRED_ALIAS)._value
        if fp_alias in self.credentials.keys():
            fp_cred = self.credentials[fp_alias]
            self.fireprox = FireProx(fp_cred)
        else:
            self.print_warning(f'Fireprox manager credential alias \'{fp_alias}\' not found!')
            self.fireprox = None

        self.modules = ModManager(self, search_dirs)
        self._logger.info(f'Loaded {len(self.modules)} modules into the framework')


    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} LoadedModules={len(self.modules)} Version=\'stratustryke v{stratustryke.__version__}\'>'


    def spool_message(self, msg: str) -> None:
        if self.spooler != None:
            with open(self.spooler.absolute(), self.spool_mode) as spooler:
                spooler.write(msg)
                

    # === various logging and print utility methods === #
    def print_error(self, msg: str) -> None:
        '''Prints (magenta) error message: [x] {msg}'''
        use_color = self._config.get_val(StratustrykeFramework.CONF_COLORED_OUTPUT)
        prefix = colored('[x]', 'magenta', attrs=('bold',)) if use_color else '[x]'
        output = f'{prefix} {msg}{os.linesep}'

        self._logger.error(output) # errors will always be passed to logger as well

        self._stdout.write(output)
        self._stdout.flush()
        return self.spool_message(output)


    def print_status(self, msg: str) -> None:
        '''Prints (blue) status message: [*] {msg}'''
        use_color = self._config.get_val(StratustrykeFramework.CONF_COLORED_OUTPUT)
        prefix = colored('[*]', 'blue', attrs=('bold',)) if use_color else '[*]'
        output = f'{prefix} {msg}{os.linesep}'

        self._stdout.write(output)
        self._stdout.flush()
        return self.spool_message(output)


    def print_warning(self, msg: str) -> None:
        '''Prints (yellow) warning message: [!] {msg}'''
        use_color = self._config.get_val(StratustrykeFramework.CONF_COLORED_OUTPUT)
        prefix = colored('[!]', 'yellow', attrs=('bold',)) if use_color else '[!]'
        output = f'{prefix} {msg}{os.linesep}'

        self._stdout.write(output)
        self._stdout.flush()

        return self.spool_message(output)


    def print_success(self, msg: str) -> None:
        '''Prints (green) success message: [+] {msg}'''
        use_color = self._config.get_val(StratustrykeFramework.CONF_COLORED_OUTPUT)
        prefix = colored('[+]', 'green', attrs=('bold',)) if use_color else '[+] '
        output = f'{prefix} {msg}{os.linesep}'
        
        self._stdout.write(output)
        self._stdout.flush()
        return self.spool_message(output)
    

    def print_failure(self, msg: str) -> None:
        '''Prints (red) failure (not error!) message: [-] {msg}'''
        use_color = self._config.get_val(StratustrykeFramework.CONF_COLORED_OUTPUT)
        prefix = colored('[-]', 'red', attrs=('bold',)) if use_color else '[-] '
        output = f'{prefix} {msg}{os.linesep}'
        
        self._stdout.write(output)
        self._stdout.flush()
        return self.spool_message(output)


    def print_line(self, msg: str) -> None:
        '''Prints line to the stdout with regular text: {msg}'''
        output = f'{msg}{os.linesep}'
        
        self._stdout.write(output)
        self._stdout.flush()
        return self.spool_message(output)


    def get_module_logger(self, mod_name: str) -> logging.Logger:
        '''Returns a logger for each module'''
        return logging.getLogger(f'stratustryke.module.{mod_name}')

    # === Module load / reload === #

    def load_module(self, mod_path: str, reload_mod: bool = False):
        '''Loads a module into the framework and returns an instance of its Module class'''
        mod_package = f'{self.__package__}.modules.{mod_path}'.replace('/','.')
        try:
            module = importlib.import_module(mod_package)
            if reload_mod:
                importlib.reload(module)

            instance = module.Module(self)
        except Exception as err:
            self._logger.error(f'Failed to load module: \'{mod_path}\'', exc_info=True)
            raise lib.FrameworkRuntimeError(f'Failed to load module: \'{mod_path}\'')

        return instance


    def reload_module(self, mod_path: str = None) -> bool:
        '''Reloads a module in the framework (default: current module)
        :return: bool True for success, False for error'''

        # Check if we are reloading the current module
        if mod_path == None:
            if self.current_module != None:
                mod_path = self.current_module.name
            else: # No module specified to reload and no module currently loaded
                self._logger.warning(f'StratustrykeFramework.reload_module() called without active module or specified module to reload')
                return False

        # Ensure module requested for reload is already loaded
        if mod_path not in self.modules:
            self._logger.error(f'Invalid module \'{mod_path}\' requested for reload while not in framework')
            raise lib.FrameworkRuntimeError(f'Invalid module: \'{mod_path}\' requested for reload')

        self._logger.info(f'Reloading \'{mod_path}\' module')

        instance = self.load_module(mod_path, True)
        # Ensure Module class instance has required attributes
        if not isinstance(instance, StratustrykeModule): # Modules must inherit StratustrykeModule
            self._logger.error(f'Module: \'{mod_path}\' does not inherit from stratustryke.core.module.StratustrykeModule class')
            raise lib.FrameworkRuntimeError(f'Module: \'{mod_path}\' does not inherit from stratustryke.core.module.StratustrykeModule class')
        if not isinstance(instance._options, stratustryke.core.option.Options): # options must be of Options class
            self._logger.error(f'Module: \'{mod_path}\' options are not of stratustryke.core.option.Options class')
            raise lib.FrameworkRuntimeError(f'Module: \'{mod_path}\' options are not of stratustryke.core.option.Options class')
        if not(instance._info.get('Authors', False) and instance._info.get('Details', False) and instance._info.get('References', False) and (instance.desc != False)): # Modules must specify this info
            self._logger.error(f'Module: {mod_path} does not designate necessary info - Author, Details, References')
            raise lib.FrameworkRuntimeError(f'Module: {mod_path} does not designate necessary info - Author, Details, References')
        if not hasattr(instance, 'run'): # Modules must implement run() method
            self._logger.error(f'Module: \'{mod_path}\' does not implement run() method')
            raise lib.FrameworkRuntimeError(f'Module: {mod_path} does not implement run() method')
        
        # Set name, path, and store the instance
        instance.name = mod_path.split('/')[-1]
        instance.path = mod_path
        self.modules[mod_path] = instance

        # If we just reloaded the current module, reset it's instance of the Module
        if self.current_module != None and self.current_module.path == instance.path:
            self.current_module = instance

        return True


    # === Run a module === #
    def run(self, module = None):
        '''Run a stratustryke module, return whatever is returned by the module's run() method (typically None)'''
        mod_is_ss_module = isinstance(module, StratustrykeModule)
        current_mod_is_ss_module = isinstance(self.current_module, StratustrykeModule)

        # Ensure either the passed module or current module inherits StrautstrykeModule
        if not (mod_is_ss_module or current_mod_is_ss_module):
            raise lib.FrameworkRuntimeError(f'StratustrykeFramework.run() called when nether passed module or current module inherit from stratustryke.core.module.StratustrykeModule')

        module == self.current_module if (module == None) else module

        self._logger.info(f'Running module: \'{module.path}\'')

        # Run the module
        try:
            res = module.run()
        except Exception as err:
            self._logger.error(f'Exception thrown when running module \'{module.path}\': {err}')
        
        return res


    def print_table(self, rows: list, headers: list, prefix: str = '  ', table_format: str = None):
        '''
        Prints a table to the framework
        :param rows: list[list[str]] list of rows containing a list of columns
        :param headers: list[str] containing column header names
        :param prefix: string to include before each line [default two spaces]
        :param table_format: type of table to generate'''
        table_format = self._config.get_opt(StratustrykeFramework.CONF_DEFAULT_TABLE_FORMAT) if (table_format == None) else table_format
        table_text = tabulate.tabulate(rows, headers=headers, tablefmt=table_format)
        if prefix:
            table_text = '\n'.join(f'{prefix}{line}' for line in table_text.split('\n'))
        self.print_line(table_text) # prints all table lines as they'll be merged into one string 
