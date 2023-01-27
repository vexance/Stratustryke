# Author: @vexance
# Purpose: CLI interpreter for stratustryke command prompt
# 
from __future__ import absolute_import
from __future__ import unicode_literals

from pathlib import Path
import typing
import stratustryke
import stratustryke.core.command
import stratustryke.core.framework
import stratustryke.settings
import stratustryke.core.lib
import stratustryke.core.credential
from termcolor import colored
import os
import logging

# === Utility functions for filesytem path completion === #

def complete_all_paths(str_path: str = '.') -> list:
    '''Complete paths to local filesystem docs
    :param str path: Prefix to paths which will be completed
    :return: list<str> paths which are prefixed with supplied path'''
    matches = []

    # Paths in working directory
    if str_path == '.': 
        for entry in Path('.').iterdir():
            match = f'{entry}' if (entry.is_file()) else f'{entry}{os.sep}'
            matches.append(f'./{entry}')
        
        return matches
    
    path = Path(str_path)

    # If passed a directory that doesn't exist, then return empty list
    if (str_path[-1] == os.sep) and (not path.is_dir()): 
        return [] # empty list

    if path.is_dir(): # if directory, we'll list the dir and match against all entries (similar to '.')
        dir_path = path
        file_prefix = ''
    else: # else we'll list the directory prior to the prefix and match against the prefix
        dir_path = path.parents[0] # everyting prior to last seperator
        file_prefix = str(path.parts[-1]) # everything after last seperator
    
    # List directory contents while looking for our match
    for entry in dir_path.iterdir():
        entry = entry.parts[-1]
        if entry.startswith(file_prefix):
            match = f'{dir_path/entry}' if (Path(dir_path/entry).is_file()) else f'{dir_path/entry}{os.sep}' # add seperator if directory to be added
            matches.append(match)
    
    return matches


def complete_path(str_path: str, files: bool = True, dirs: bool = True) -> list:
    '''Complete all paths, but remove files if prevented'''
    matches = complete_all_paths(str_path)
    if files and dirs:
        paths = matches
    elif dirs and not files: # remove file entries, only return directory matches
        paths = []
        for entry in matches:
            if Path(entry).is_dir():
                paths.append(entry)
    elif files and not dirs: # remove directory entries, only return file matches
        paths = []
        for entry in matches:
            if Path(entry).is_file():
                paths.append(entry)

    return paths
        

# === CLI console Interpreter - interprets stratustryke.Command objects === #
class InteractiveInterpreter(stratustryke.core.command.Command):
    ruler = '+'
    doc_header = 'Enter help <command> For Information and List of available commands:'

    def __init__(self, stdin = None, stdout = None, rc_file: str = None, log_handler = None) -> None:
        super().__init__(stdin, stdout)
        self.last_module = None
        # Setup hidden / disabled commands
        if not self.use_rawinput:
            pass
            #self._disabled_commands.append() # Not disabling any commands as of v0.0.1
        if not stratustryke.settings.on_linux:
            pass
            #self._hidden_commands.append() # Not hiding any commands on linux as of v.0.0.1
        self._hidden_commands.extend(['cd', 'ls', 'cat', 'dir', 'type', 'pwd'])

        # init logging
        self.log_handler = log_handler
        if self.log_handler == None:
            self._hidden_commands.append('logging')
        self._logger = logging.getLogger('stratustryke.interpreter')

        # init framework
        self.framework = stratustryke.core.framework.StratustrykeFramework(stdout=stdout)
        self.print_error = self.framework.print_error # magenta [x] msg
        self.print_status = self.framework.print_status # blue [*] msg
        self.print_warning = self.framework.print_warning # yellow [!] msg
        self.print_success = self.framework.print_success # green [+] msg
        self.print_failure = self.framework.print_failure # red [-] msg
        self.print_line = self.framework.print_line # regular text

        # Run resource file on launch if specified
        if rc_file:
            rc_file_exists = (Path(rc_file).exists() and Path(rc_file).is_file())
            if not rc_file_exists:
                self.print_error(f'Could not find resource file: {rc_file}')
                self._logger.error(f'Could not find resource file: {rc_file}')
            else: # found it! try and read commands...
                self.print_status(f'Running commands from resource file: {rc_file}')
                self.run_rc_file(rc_file)

        # Attempt to read commands from history
        try:
            import readline
            readline.read_history_file(str(stratustryke.core.lib.home_dir()/'history.txt'))
            readline.set_completer_delims(readline.get_completer_delims().replace('/', ''))
        except (ImportError, IOError):
            self._logger.error(f'Failed to import stratutryke history from {stratustryke.core.lib.home_dir()/"history.txt"}')


    # === Startup intro banner and CLI prompt === #

    @property
    def intro(self) -> str:
        '''Stratustryke launch intro output''' # 64 characters per line
        intro = os.linesep
        intro += '        ______           __           __           __           ' + os.linesep
        intro += '       / __/ /________ _/ /___ _____ / /_______ __/ /_____      ' + os.linesep
        intro += '      _\ \/ __/ __/ _ `/ __/ // (_-</ __/ __/ // /  \'_/ -_)     ' + os.linesep
        intro += '     /___/\__/_/  \_,_/\__/\_,_/___/\__/_/  \_, /_/\_\\__/      ' + os.linesep
        intro += '                                           /___/                ' + os.linesep
        intro += os.linesep
        intro += f'     {stratustryke.__progname__} v{stratustryke.__version__}{os.linesep}' 
        intro += f'     Loaded modules: {len(self.framework.modules)}{os.linesep}'
        return intro

    @property
    def prompt(self):
        '''The CLI prompt'''
        coloring = self.framework._config.get_val('COLORED_OUTPUT')
        prog_name = colored(stratustryke.__progname__, 'blue', attrs=('bold',)) if (coloring) else stratustryke.__progname__

        if self.framework.current_module == None:
            return f'{prog_name} > '
        else: # there's a module active
            mod_name = colored(self.framework.current_module.search_name, 'yellow') if (coloring) else self.framework.current_module.name
            return f'{prog_name} ({mod_name}) > '


    # === resource file, server, and module re-load utility === #

    def run_rc_file(self, rc_file: str):
        '''Pass to stratustryke.core.command.Command.run_rc_file()'''
        self._logger.info(f'Opening {rc_file} for command processing')
        return super().run_rc_file(rc_file)


    def serve(cls, *args, **kwargs):
        '''Pass to stratustryke.core.command.Command.serve() after setting rc_file to None'''
        init_kwargs = kwargs.pop('init_kwargs', {})
        init_kwargs['rc_file'] = None
        kwargs['init_kwargs'] = init_kwargs
        return super().serve(*args, **kwargs)


    def reload_module(self, module):
        # Check if we're reloading the current module
        mod_is_current_module = (self.framework.current_module != None) and (module.path == self.framework.current_module.path)

        try: 
            module = self.framework.reload_module(module.search_name)
        except Exception as err:
            self.print_error(f'Exception thrown when reloading module: \'{module.name}\'')
            self.print_error(f'{err}')
            self._logger.error(f'Exception thrown when reloading module: \'{module.name}\'')
            return None
        
        self.print_line(f'Reloaded module: \'{module.name}\'')
        self._logger.info(f'Reloaded module: \'{module.name}\'')

        # Update current module instance if we just reloaded it
        if mod_is_current_module:
            self.framework.current_module = module
        return module


    def precmd(self, line):
        if self.framework.spooler != None:
            self.framework.spooler.write(f'{self.prompt}{line}{os.linesep}')
        return super().precmd(line)


    # ================================================ #
    #                Framework Commands                #
    # ================================================ #

    # Command: banner
    # Action: prints the startup intro banner, showing ascii text art, version, and number of modules loaded
    # Syntax: 'banner'

    @stratustryke.core.command.command('Display initial startup banner')
    def do_banner(self, args):
        self.print_line(self.intro)
    

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


    # Command: cd
    # Action: Changes the current working directory context in the stratustryke interpreter
    # Syntax: 'cd <directory>'
    # Text Completion: paths to local filesystem directories

    @stratustryke.core.command.command('Change current working directory')
    @stratustryke.core.command.argument('path', nargs='?', help = 'Path to change directories to')
    def do_cd(self, args):
        if not args.path:
            self.print_line(f'Command \'cd\' requires a path{os.linesep}')
            return
        if not Path(args.path).is_dir():
            self.print_line(f'Provided path \'{args.path}\' is not a directory{os.linesep}')
            return
        
        os.chdir(args.path) # cd

    def complete_cd(self, text, line, begidx, endidx):
        return complete_path(text, files=False, dirs=True)


    # Command: pwd
    # Action: Prints the current working directory for the stratustryke interpreter context
    # Syntax: 'pwd'

    @stratustryke.core.command.command('Print current working directory')
    def do_pwd(self, args):
        self.print_line(f'{os.getcwd()}{os.linesep}')

    
    # Command: ls
    # Action: Prints the contents of the specified or current directory for the stratustryke interpreter
    # Syntax: 'ls', 'ls <path>'
    # Text Completion: paths to local filesystem directories
    # Aliases: 'dir'

    @stratustryke.core.command.command('List directory contents')
    @stratustryke.core.command.argument('path', nargs='?', help = 'Directory to list contents of')
    def do_ls(self, args):
        if not args.path:
            args.path = '.'
        if args.path[-1] != os.sep:
            args.path += os.sep
        path = Path(args.path)
        if not path.is_dir():
            self.print_line(f'Provided path \'{args.path}\' is not a directory{os.linesep}')
            return
        
        if not path.is_absolute():
            path = Path(os.getcwd()/path).absolute()

        coloring = self.framework._config.get_val('COLORED_OUTPUT')
        for entry in path.iterdir():
            item = f'{entry.parts[-1]}'
            if coloring and entry.is_dir():
                item = colored(item, 'blue', attrs=('bold',))
            self.print_line(f'  {args.path}{item}')

        self.print_line('') # make space for prompt

    def complete_ls(self, text, line, begidx, endidx):
        return complete_path(text, files=False, dirs=True)

    def do_dir(self, args):
        '''Alias for 'ls' command'''
        return self.do_ls(args)
    
    def complete_dir(self, text, line, begidx, endidx):
        return self.complete_ls(text, line, begidx, endidx)


    # Command: cat
    # Action: Prints contents of a file on the local filesystem
    # Syntax: 'cat <file>', 'cat <file1> <file2> <etc>'
    # Text Completion: paths to local filesystem files
    # Aliases: 'type'

    @stratustryke.core.command.command('Print a file to the interpreter output')
    @stratustryke.core.command.argument('file', nargs='*', help = 'File(s) to print contents of')
    def do_cat(self, args):
        if not args.file:
            self.print_line(f'Command \'cat\' requires a file passed as an arguement{os.linesep}')
            return

        for item in args.file:
            path = Path(item).absolute()
            if path.is_file():
                with open(path, 'r') as file:
                    lines = file.readlines()
                    for line in lines:
                        self.print_line(line.strip(os.linesep))
            else:
                self.print_line(f'File \'{path}\' not found{os.linesep}')

    def complete_cat(self, text, line, begidx, endidx):
        return complete_path(text, files=True, dirs=True)

    def do_type(self, args):
        '''Alias for 'cat' command'''
        return self.do_cat(args)

    def complete_type(self, text, line, begidx, endidx):
        return self.complete_cat(text, line, begidx, endidx)


    # Command: exit
    # Action: Closes the stratustryke interpreter
    # Syntax: 'exit'

    @stratustryke.core.command.command('Exit the Stratustryke interpreter')
    def do_exit(self, args):
        self._logger.info('Recevied exit command')
        # Add closing quotes here?
        
        if self.framework.spooler != None:
            self.framework.spooler.close()
            self.framework.spooler = None

        try: # Try to copy command history to 'home/<user>/.local/strautsryke/history.txt
            import readline
            readline.write_history_file(str(stratustryke.core.lib.home_dir()/'history.txt'))
        except (ImportError, IOError):
            self._logger.error(f'Exception thrown while writing command history to {stratustryke.core.lib.home_dir()/"history.txt"}')
        
        super().do_exit(args)


    # Command: help
    # Action: Displays commands or help information for commands
    # Syntax: 'help', 'help <command>'

    def do_help(self, arg: str):
        super().do_help(arg)


    # Command: 'loglevel'
    # Action: Displays or updates the logger's log level threshold
    # Syntax: 'loglevel', 'loglevel <level>'
    # Text Completion: log level options: debug, info, warning, error, critical

    @stratustryke.core.command.command('Set or show log level options / current setting')
    @stratustryke.core.command.argument('level', nargs='?', help = 'Log level to set [DEBUG, INFO, WARNING, ERROR, CRITICAL]')
    def do_loglevel(self, args):
        # Check that the log handler exists
        if self.log_handler == None:
            self.print_error(f'Framework log handler is not defined{os.linesep}')
            return

        levels_dict = {10: 'DEBUG', 20: 'INFO', 30: 'WARNING', 40: 'ERROR', 50: 'CRITICAL'}
        if args.level == None: # No log level specified, display the current value
            current = self.log_handler.level
            current = levels_dict.get(current, 'UNKNOWN')
            self.print_line(f'Current effective log level threshold is: {current}{os.linesep}')
            return

        # New log level specified - check for validity 
        new = args.level.upper()
        new = next((level for level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL') if level.startswith(new)), None) # iterate through potential options
        if new == None:
            self.print_line(f'Invalid log level \'{new}\' is not in [DEBUG, INFO, WARNING, ERROR, CRITICAL]{os.linesep}')
            return

        # Get associated int value from logging package
        self.log_handler.setLevel(getattr(logging, new))
        self.print_line(f'Updated effective log level to logging.{new}{os.linesep}')

    def complete_loglevel(self, text, line, begidx, endidx):
        '''Return text completion for logging options'''
        return [i for i in ['debug', 'info', 'warning', 'error', 'critical'] if i.startswith(text.lower())]

    
    # Command: 'info'
    # Action: displays module information and module options for the current module or specified module
    # Syntax: 'info', 'info <module>'
    # Text Completion: Modules loaded into the framework

    @stratustryke.core.command.command('Display module information')
    @stratustryke.core.command.argument('module', nargs = '?', help = 'Module for which to display information for')
    def do_info(self, args):
        
        # no module supplied and no current module set
        if args.module == None: # no module specifed
            if self.framework.current_module == None: # And no current module set
                self.print_line('No current module or module supplied to show information for')
                return
            mod = self.framework.current_module

        elif args.module in self.framework.modules: # module specified is loaded
            mod = self.framework.modules[args.module]
        
        else: # module specified doesn't exist / isn't loaded
            self.print_line(f'Module: \'{args.module}\' not found')
            return

        # Print module information (authors, details, name, references, description)
        for line in mod.show_info():
            self.print_line(line)

        # Then print module options
        self.print_line('') # create space
        self.print_line('  Module options:')
        self.print_line('')
        masking = self.framework._config.get_val('MASK_SENSITIVE')
        rows = mod.show_options(masking)
        headers = ['Module Name', 'Value', 'Required', 'Description']
        self.framework.print_table(rows, headers, '  ')

        self.print_line('') # Create space for prompt

    def complete_info(self, text, line, begidx, endidx):
        '''Return text completion for info module options'''
        return [i for i in self.framework.modules.keys() if i.startswith(text)]


    # Command: 'previous'
    # Action: selects the last module as the current module, sets current module to the last module
    # Syntax: 'previous'

    @stratustryke.core.command.command('Use the last prior module')
    def do_previous(self, args):
        if self.last_module == None: # if this is NOT none, the framework's current will also not be none
            self.print_line('No module previously selected')
            return
        
        # switch last and current modules
        self.last_module, self.framework.current_module = self.framework.current_module, self.last_module


    # Command: validate
    # Actions: Performs validation checks of options against the current module
    # Syntax: 'validate'

    @stratustryke.core.command.command('Perform module validation checks')
    def do_validate(self, args):
        if self.framework.current_module == None:
            self.print_line('No module currently selected')
            return

        success, msg = self.framework.current_module.validate_options()
        if success:
            self.print_status('Module validation successful')
        else:
            self.print_error(msg)


    # Command: back
    # Action: Unsets the currently selected module, returning user to default prompt
    # Syntax: 'back'

    @stratustryke.core.command.command('Close the module and return to default framework context')
    def do_back(self, args):
        self.framework.current_module = None


    # Command: 'reload'
    # Action: Reloads a module in the framework, resetting options
    # Syntax: 'reload', 'reload <module>'
    # Text Completion: modules loaded into the framework
    # Todo: Broken - disabling for now; Not working currently

    # @stratustryke.core.command.command('Reloads a module in the framework')
    # @stratustryke.core.command.argument('module', nargs='?', help = 'The module to re-load')
    # def do_reload(self, args):
    #     if args.module != None:
    #         if args.module not in self.framework.modules:
    #             self.print_line(f'Module: \'{args.module}\' not found')
            
    #         mod = self.framework.modules[args.module]

    #     elif self.framework.current_module != None: # Use current module if no module arg specified
    #         mod = self.framework.current_module

    #     else: # Current module not set and no <module> arg supplied
    #         self.print_line(f'Must specifiy module to reload or run command \'use\' prior to reloading a module')
    #         return
        
    #     self.reload_module(mod)

    # def complete_reload(self, text, line, begidx, endidx):
    #     return [i for i in self.framework.modules.keys() if i.startswith(text)]
    

    # Command: 'set'
    # Action: Updates the value for a module's option
    # Syntax: 'set <option-name> <new-value>'
    # Text Completion: Options for the current module

    @stratustryke.core.command.command('Set the value for a module\'s option')
    @stratustryke.core.command.argument('option_name', metavar='option', help = 'Name of option to set value for')
    @stratustryke.core.command.argument('option_value', metavar='value', help = 'New value to set the option to')
    def do_set(self, args):
        if self.framework.current_module: # get options for current module
            opts = self.framework.current_module._options
            opt_names = self.framework.current_module._options.keys()
        else:
            self.print_line('No module currently in use')
            return

        # Make sure the opt is one of the module's options
        if args.option_name.upper() not in opt_names:
            self.print_line(f'Unknown option: {args.option_name}')
            return

        try:
            success = opts.set_opt(args.option_name, args.option_value)
        except TypeError as err:
            self.print_line(f'Invalid data type for \'{args.option_name}\': {args.option_value}')
            self._logger.error(f'Invalid data type for \'{args.option_name}\': {args.option_value}')
            return
        
        if success:
            self.print_line(f'  {args.option_name} => {args.option_value}')

    def complete_set(self, text, line, begidx, endidx):
        completions = [f'{i} ' for i in self.framework.current_module._options.keys() if i.startswith(text.upper())]
        if 'true'.startswith(text.lower()):
            completions.append('true')
        if 'false'.startswith(text.lower()):
            completions.append('false')
        return completions


    # Command: 'options'
    # Action: Displays options for the current or specified module
    # Syntax: 'options', 'options <module>'
    # Text Completion: modules loaded into the framework

    @stratustryke.core.command.command('Show options for the current or specified module')
    @stratustryke.core.command.argument('module', nargs='?', help = 'Module to display options for')
    def do_options(self, args):      
        # no module supplied and no current module set
        if args.module == None: # no module specifed
            if self.framework.current_module == None: # And no current module set
                self.print_line('No current module or module supplied to show information for')
                return
            mod = self.framework.current_module

        elif args.module in self.framework.modules: # module specified is loaded
            mod = self.framework.modules[args.module]
        
        else: # module specified doesn't exist / isn't loaded
            self.print_line(f'Module: \'{args.module}\' not found')
            return

        # Print module options
        self.print_line('') # create space
        self.print_line('  Module options:')
        self.print_line('')
        masking = self.framework._config.get_val('MASK_SENSITIVE')
        rows = mod.show_options(masking)
        headers = ['Module Name', 'Value', 'Required', 'Description']
        self.framework.print_table(rows, headers, '  ')

        self.print_line('') # Create space for prompt

    def complete_options(self, text, line, begidx, endidx):
        return [i for i in self.framework.modules.keys() if i.startswith(text)]


    # Command: 'show'
    # Action: Displays various types of information
    # Syntax: 'show modules', 'show config', 'show options', 'show info'
    # Text Completion: modules, config, options, info

    @stratustryke.core.command.command('Show requested information for modules, configurations, or module options')
    @stratustryke.core.command.argument('what', choices=('modules', 'config', 'options', 'info'), help = 'Type of information to display')
    def do_show(self, args):
        ''''Command: 'show <what>' displays information based off what information is requested'''
        headers, rows = [], []
        choice = args.what.lower()
        self.print_line('') # make space for the table

        # list modules in the framework
        if choice == 'modules': 
            self.print_line(f'  Displaying framework modules...{os.linesep}')
            rows = [[module.search_name, module.desc] for module in self.framework.modules.values()]
            headers = ['Module Name', 'Description']
        
        # show framework config options
        elif choice == 'config':
            self.print_line(f'  Framework configuration options:{os.linesep}')
            rows = self.framework._config.show_options()
            headers = ['Name', 'Value', 'Required', 'Description']
        
        elif choice == 'options':
            if self.framework.current_module == None:
                self.print_line('No module currently selected')
                return
            self.print_line(f'  Module options:{os.linesep}')
            masking = self.framework._config.get_val('MASK_SENSITIVE')
            rows = self.framework.current_module.show_options(masking)
            headers = ['Name', 'Value', 'Required', 'Description']

        elif choice == 'info':
            return self.do_info(args)

        else:
            self.print_line(f'Invalid selection \'{args.choice}\' for show command')
            return

        rows = sorted(rows, key = lambda row: row[0]) # sort off first column in the rows (mod or opt name)
        self.framework.print_table(rows, headers, '  ')
        self.print_line('') # make room for prompt

    def complete_show(self, text, line, begidx, endidx):
        '''Text completion for show command'''
        return [i for i in ['modules', 'config', 'options', 'info'] if i.startswith(text.lower())]
            

    # Command: 'config'
    # Action: Display or update framework configuration options
    # Syntax: 'config', 'config <name> <new-value>'
    # Text Completion: framework configuration option names

    @stratustryke.core.command.command('Show or set framework configuration options')
    @stratustryke.core.command.argument('config_name', metavar='config', default=None, nargs='?', help='If setting a config, the config option to update')
    @stratustryke.core.command.argument('config_val', metavar='value', default=None, nargs='?', help='If setting a config, the value to update it to')
    def do_config(self, args):
        '''Command: 'config <action> [name] [val]' shows or sets framework config options'''

        if args.config_name == None:
            self.print_line(f'{os.linesep}  Framework configuration options:{os.linesep}')
            rows = self.framework._config.show_options()
            headers = ['Name', 'Value', 'Required', 'Description']

            rows = sorted(rows, key = lambda row: row[0]) # sort by opt name
            self.framework.print_table(rows, headers, '  ')
            self.print_line('') # make room for prompt
            return

        elif args.config_name != None :
            if args.config_val == None:
                self.print_line('Must specify configuration name and value')
                return

            opts = self.framework._config
            opt_names = self.framework._config.keys()

            # Invalid config opt
            if args.config_name.upper() not in opt_names:
                self.print_line(f'Unknown configuration option: {args.config_name}')
                return

            # Try and update it
            try:
                success = self.framework._config.set_opt(args.config_name, args.config_val)
            except (TypeError) as err:
                self.print_line(f'Invalid data type for \'{args.config_name}\': {args.config_val}')
                self._logger.error(f'Invalid data type for \'{args.config_name}\': {args.config_val}')
                return

            if success:
                self.print_line(f'  {args.config_name} => {args.config_val}')
                return
            
        else:
            self.print_line(f'Unknown config command action \'{args.cmd_action}\' not in [\'show\', \'set\']')

    def complete_config(self, text, line, begidx, endidx):
        completions = [i for i in self.framework._config.keys() if i.startswith(text.upper())]
        if 'true'.startswith(text.lower()):
            completions.append('true')
        if 'false'.startswith(text.lower()):
            completions.append('false')
        return completions


    # Command: 'use'
    # Action: selects a module as the current module
    # Syntax: 'use <module>'
    # Text Completion: modules loaded into the framework

    @stratustryke.core.command.command('Select a module for use')
    @stratustryke.core.command.argument('module', help = 'The module to select')
    def do_use(self, args):
        if args.module not in self.framework.modules:
            self.print_line(f'Could not find module: \'{args.module}\'')
            self._logger.error(f'Unable to select module: \'{args.module}\'; module not found')
            return
        
        self.last_module = self.framework.current_module
        self.framework.current_module = self.framework.modules[args.module]

    def complete_use(self, text, line, begidx, endidx):
        return [i for i in self.framework.modules.keys() if i.startswith(text)]


    # Command: 'creds'
    # Action: List credential aliases or attempt to load cred values into a module
    # Syntax: 'creds', 'creds <alias>'
    # Text Complete: Saved credential aliases

    @stratustryke.core.command.command('Show or load credentials from the stratustryke credstore')
    @stratustryke.core.command.argument('alias', nargs='?', help = 'Credentials to load for the selected module')
    def do_creds(self, args):
        if args.alias == None:
            workspace = self.framework._config.get_val('WORKSPACE')
            aliases = self.framework.credentials.list_aliases(workspace)
            
            headers = ['Cred Type', 'Alias']
            rows = []
            for entry in aliases:
                cred = self.framework.credentials[entry]
                cred_type = self.framework.credentials.get_cred_type(cred)
                rows.append([cred_type, entry])
            
            self.print_line(f'Listing credentials stored for the current workspace...{os.linesep}')
            self.framework.print_table(rows, headers)
            self.print_line('')
            return
        
        if self.framework.current_module == None:
            self.print_line('No module currently selected to load credentials for')
            return

        elif args.alias in self.framework.credentials.keys():
            cred = self.framework.credentials[args.alias]

            try:
                self.framework.credentials.set_module_creds(self.framework.current_module, cred)
            except Exception as err:
                self.print_error(f'Error loading credentials into module')
                self.print_error(f'{err}')
                self._logger.error(f'Error loading credentials into module')
                self._logger.error(f'{err}')
                return
            
            self.print_status(f'Loaded credentials for \'{args.alias}\'')


        else:
            self.print_line(f'Credential alias \'{args.alias}\' not found')
        
        return
        
    def complete_creds(self, text, line, begidx, endidx):
        workspace = self.framework._config.get_val('WORKSPACE')
        return [i for i in self.framework.credentials.list_aliases(workspace) if i.startswith(text)]


    # Command: 'rmcred'
    # Action: Deletes a credential from the credstore
    # Syntax: 'rmcred <alias>'
    # Text Complete: Saved Credential aliases

    @stratustryke.core.command.command('Remove a credential from the credstore')
    @stratustryke.core.command.argument('alias', help='Credential to remove from the credstore')
    def do_rmcred(self, args):
        if args.alias not in self.framework.credentials.keys():
            self.print_line(f'Credential alias \'{args.alias}\' not found')
            return

        self.framework.credentials.remove_credential(args.alias)

    def complete_rmcred(self, text, line, begidx, endidx):
        workspace = self.framework._config.get_val('WORKSPACE')
        return [i for i in self.framework.credentials.list_aliases(workspace) if i.startswith(text)]


    # Command: 'spool'
    # Action: Enables or disables spooling of output to a file
    # Syntax: 'spool <filename>', 'spool off'
    # Text Completion: directories on the local filesystem
    
    @stratustryke.core.command.command('Enable or disable spooling of stratustryke output to a file')
    @stratustryke.core.command.argument('path', help = '\'off\' or file to enable / switch spooling to')
    def do_spool(self, args):
        if args.path.lower() == 'off':
            if self.framework.spooler != None:
                self.framework.spooler.close()
                self.framework.spooler = None
            
            self.print_status('Spooling of stratustryke output disabled')
        
        elif self.framework.spooler != None: # already spooling
            self.print_status(f'Already spooling output to a file')
            return

        else: # we'll try and create the file handle
            spool_overwrite = self.framework._config.get_val('SPOOL_OVERWRITE')
            mode = 'w' if (spool_overwrite) else 'a'
            path = Path(args.path)

            if path.exists() and path.is_dir(): # 
                self.print_line(f'Specfied path is a directory')
                return

            elif path.exists() and path.is_file():
                if spool_overwrite:
                    self.print_status(f'Overwriting file {path.absolute()}')
                else:
                    self.print_status(f'Appending to file: {path.absolute()}')

            self.print_status(f'Spooling to {path.absolute()}')
            try:
                self.framework.spooler = open(path, mode)
            except Exception as err:
                self.print_error(f'{err}')
                self.framework.spooler = None
                return

    def complete_spool(self, text, line, begidx, endidx):
        completions = complete_path(text, True, True)
        if 'off'.startswith(text):
            completions.append('off')
        return completions

    # Command: 'run'
    # Action: Runs the current module with the option values specified
    # Syntax: 'run'
    # Aliases: 'execute'
    # Todo: error in validate_options()

    @stratustryke.core.command.command('Execute the currently selected module')
    def do_run(self, args):
        if self.framework.current_module == None:
            self.print_line('No module currently selected')

        force_validate = self.framework._config.get_val('FORCE_VALIDATE_OPTIONS')
        if force_validate:
            self.print_status('Validating module options')
            valid, msg = self.framework.current_module.validate_options()
            if not valid:
                self.print_error(f'{msg}{os.linesep}')
                return
            self.print_status(f'Module options passed validation{os.linesep}')
        
        self.print_status(f'Running module...{os.linesep}')

        try:
            res = self.framework.current_module.run()
        except KeyboardInterrupt:
            self.print_line('')
            return
        except Exception as err:
            self.print_error(f'Exception thrown while running module \'{self.framework.current_module.name}\'')
            self.print_error(f'{err}')
            res = None

        
