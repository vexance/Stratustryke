# Author: @vexance
# Purpose: Command parser for stratustryke console
# 

import argparse
import sys
import shlex
import typing
import cmd
import logging
import socket 
import ssl


class ArgParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        self.stdout = kwargs.pop('stdout', sys.stdout)
        super().__init__(*args, **kwargs)

    def error(self, msg: str) -> typing.NoReturn:
        '''Exit with status code 2 and designated error message'''
        self.print_usage()
        self.exit(2, f'{self.prog}: error: {msg}\n')

    def exit(self, status: int = 0, msg: str = None) -> typing.NoReturn:
        if msg:
            self.stdout.write(msg)
        raise ArgParserExit(status, msg)

    def print_help(self) -> None:
        super().print_help(file = self.stdout)

    def print_usage(self) -> None:
        super().print_usage(file = self.stdout)

class ArgParserExit(Exception):
    def __init__(self, status: int = 0, msg: str = None):
        self.status = status
        self.message = msg

class StratustrykeExit(Exception):
    def __init__(self, status: int = 0, msg: str = None) -> None:
        self.status = status
        self.message = msg

class _Command(object):
    def __init__(self, callback = None, name = None):
        self._arguments = []
        self.callback = callback
        name = name if (name != None) else callback.__name__[3:] # callbacks will be functions start with do_COMMAND
        self.parser = ArgParser(prog=name)

    def _wrapper(self, inst, args):
        parser = self.parser
        
        try: # Attempt to parse args with shell-like syntax
            args = shlex.split(args)
        except ValueError as err: # parsing failed
            msg = 'Failed to parse args'
            msg = f'{msg}\n' if (not err.args) else f'{msg} ({err.args[0]})\n'
            inst.stdout.write(msg)
            return
        
        # Get instance of ArgParser & set appropriate stdout
        parser.stdout = inst.stdout
        
        try: # Parse with argparse
            args = parser.parse_args(args)
        except ArgParserExit:
            return
        
        # Call callback function
        return self.callback(inst, args)

    def add_argument(self, *args, **kwargs):
        self._arguments.append((args, kwargs))

    def wrapper(self):
        self._arguments.reverse()
        for args, kwargs in self._arguments:
            self.parser.add_argument(*args, **kwargs)

        def wrapper_function(*args, **kwargs):
            return self._wrapper(*args, **kwargs)
        wrapper_function.__doc__ = self.parser.format_help()
        return wrapper_function

# Used to define custom interpreter command arguments
def argument(*args, **kwargs):
    def decorator(command):
        if not isinstance(command, _Command): # if this isn't a _Command class obj
            command = _Command(command)

        command.add_argument(*args, **kwargs)
        return command
    return decorator

# used to define custom interpreter commands / parsers
def command(desc: str = None):
    def decorator(command):
        if not isinstance(command, _Command):
            command = _Command(command)
        command.parser.description = desc
        return command.wrapper()
    return decorator

# defines parser epilogs for interpreter commands
def epilog(text: str):
    def decorator(command):
        if not isinstance(command, _Command):
            command = _Command(command)
            command.parser.epilog = text
            return command
    return decorator


class Command(cmd.Cmd):
    def __init__(self, stdin = None, stdout = None, **kwargs):
        super().__init__(stdin=stdin, stdout=stdout, **kwargs)
        if stdin != None:
            self.use_rawinput = False
        self._hidden_commands = ['EOF']
        self._disabled_commands = []
        self.__package__ = '.'.join(self.__module__.split('.')[0:-1])

    def cmdloop(self):
        while True:
            try:
                super().cmdloop()
            except KeyboardInterrupt as err:
                self.print_line('')
                self.print_error('Please use \'exit\' to quit.')
            except StratustrykeExit as err:
                if err.status != 0: # non-default exit
                    self.print_error(f'{err.message} with status code: {err.status}')
                break
            except Exception as err:
                self.print_error(f'Exception thrown: {err}')
        # returns NoneType


    def get_names(self):
        commands = super().get_names()
        # Remove any hidden or disabled commands from the list
        to_remove = self._hidden_commands + self._disabled_commands
        for entry in to_remove:
            if f'do_{entry}' in commands:
                commands.remove(f'do_{entry}')
        return commands

    def emptyline(self):
        # override super().emptyline() to do nothing rather than repeat last line 
        pass

    def help_help(self):
        self.do_help('') # 

    def precmd(self, line):  # use this to allow using '?' after the command for help
        tmp_line = line.split()
        if not tmp_line:
            return line
        if tmp_line[0] in self._disabled_commands:
            self.default(tmp_line[0])
            return ''
        if len(tmp_line) == 1:
            return line
        if tmp_line[1] == '?':
            self.do_help(tmp_line[0])
            return ''
        return line

    def do_exit(self, args):
        raise StratustrykeExit(0, 'Closing stratustryke interpreter')

    def do_EOF(self, args):
        '''Exits interpreter - for use with resource files'''
        self.print_line('')
        return self.do_exit('')

    def run_rc_file(self, rc_file: str):
        '''Run commands as written in a resource file'''
        with open(rc_file, 'r') as file:
            for line in file.readlines():
                line = line.strip()
                if (not len(line)) or (line[0] == '#'):
                    continue # skip empty or commented lines

                self.print_line(f'{self.prompt} {line}')
                self.onecmd(line)
        return True

    def serve(cls, addr, run_once = False, log_level = None, use_ssl = False, ssl_cert = None, init_kwargs = None):
        init_kwargs = {} if (init_kwargs == None) else init_kwargs
        __package__ = '.'.join(cls.__module__.split('.')[0:-1])
        logger = logging.getLogger(f'{__package__}.interpreter.server')

        srv_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv_socket.bind(addr)

        # Listen!
        logger.info(f'Listening for connections on {addr[0]}:{addr[1]}')
        srv_socket.listen(1)
        while True:
            try:
                client_sock, client_addr = srv_socket.accept()
            except KeyboardInterrupt:
                break
            # Connection received
            logger.info(f'Connection received from {client_addr[0]}:{client_addr[1]}')

            # Prep socket r/w files
            if use_ssl:
                ssl_sock = ssl.wrap_socket(client_sock, server_side=True, certfile=ssl_cert)
                ins = ssl_sock.makefile('r', 1)
                outs = ssl_sock.makefile('w', 1)
            else:
                ins = client_sock.makefile('r', 1)
                outs = client_sock.makefile('w', 1)
            
            # Setup socket logger
            log_stream = logging.StreamHandler(outs)
            if log_level != None:
                log_stream.setLevel(log_level)
            log_stream.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
            logging.getLogger('').addHandler(log_stream)

            # Begin command loop for clinet
            interpreter = cls(stdin = ins, stdout = outs, **init_kwargs)
            try:
                interpreter.cmdloop()
            except socket.error as err:
                log_stream.close()
                logging.getLogger('').removeHandler(log_stream)
                logger.warning('Socket error during the main interpreter loop')
                continue
            
            # Interpreter command loop exited properly
            log_stream.flush()
            log_stream.close()
            logging.getLogger('').removeHandler(log_stream)

            # Close socket connections
            outs.close()
            ins.close()
            client_sock.shutdown(socket.SHUT_RDWR)
            client_sock.close()
        # End serve loop

        # Shutdown cmdloop server
        srv_socket.shutdown(socket.SHUT_RDWR)
        srv_socket.close()
