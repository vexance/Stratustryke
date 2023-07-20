# Author: @vexance
# Purpose: Class definition for module option parameters
# Credit: Heavily inspired by @zeroSteiner's Options class for Termineter
#

from re import match
import typing
from stratustryke.core.lib import StratustrykeException

class Option:
    '''Module or framework option'''

    def __init__(self, name: str, opt_type: str, desc: str = '', required: bool = False, default : typing.Any = None, regex: str = '', sensitive : bool = False) -> None:
        self._name = name
        self._desc = desc
        self._is_required = required
        self._opt_type = opt_type
        self._default = default # default value; doesn't change
        self._value = default # current value; can change
        self._regex = regex
        self._sensitive = sensitive # Flags an options as sensitive (used in show_options() to mask the value if configured)


    # String representation of class object instantiation
    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} name=\'{self._name}\', value=\'{self._value}\'>'


    def unset(self) -> None:
        '''Sets value for the option to None'''
        self._value = None


    def reset(self) -> None:
        '''Sets current value to the default value'''
        self._value = self._default

    def str_val(self) -> str:
        '''Return string representation of value'''
        if self._value == None:
            return ''
        if self._opt_type == 'bool':
            return 'True' if (self._value) else 'False'
        return str(self._value)


    def masked(self) -> str:
        '''For string type options, returns a value with most characters masked as dots.
        Three - Five character strings show the first and last characters.
        Six - Eight character strings show the first two and last two characters.
        Nine - Nineteen character strings show the first and last three characters.
        20+ character strings show the first and last four characters'''
        if self._opt_type == 'bool':
            return 'True' if (self._value) else 'False'
        if not self._opt_type == 'str':
            return str(self._value) # cast ints and floats to string
        
        if self._value == None:
            return ''
            
        length = len(self._value)
        if length < 3 or self._value == None: # 0-2 character strings; no point masking really
            return self._value
        elif length < 6: # 3-45 characters; show first & last
            return f'{self._value[0]}{"."*(length-2)}{self._value[-1]}'
        elif length < 9: # 6-8 characters; show first & last 2
            return f'{self._value[0:2]}{"."*(length-4)}{self._value[-2:]}'
        elif length < 20: # 9 - 19 characters; show first & last 3
            return f'{self._value[0:3]}{"."*(length-6)}{self._value[-3:]}'
        else: # 20+ characters; show first & last 4
            return f'{self._value[0:4]}{"."*(length-8)}{self._value[-4:]}'


    def validate(self) -> tuple:
        '''Perform validation against the option\'s regular expression string. Returns success status as well as an error message OR None
        :rtype: (bool, str | None)
        '''
        if self._value == None and self._is_required: # Empty and required
            return (False, f'Required option \'{self._name}\' is empty.')
        elif self._opt_type == 'str' and self._value != None and self._regex != '': # Not empty string & regex is specified
            status = match(self._regex, self._value)
            if not status:
                return (False, f'Option \'{self._name}\' must match regular expression \'{self._regex}\'')
        
        return (True, None)

# End class Option


class Options:
    '''Container for a collection of Option objects'''
    
    def __init__(self):
        '''Creates an empty dictionary for future options'''
        self.options : dict = {}

    # Option / option value getters
    def get_opt(self, name: str) -> Option:
        '''Return the instance of a designated Option
        :return: Option | None : instance of the Option object'''
        name = name.upper()
        return self.options.get(name, None)


    def get_val(self, name: str) -> str:
        '''Return's specified option's current value'''
        opt = self.get_opt(name)
        if opt != None:
            return opt._value
        else:
            return None


    def get_all(self) -> list:
        '''Returns a list of options in the container
        :rtype: <list<Option>> List of options in the container'''
        options = []
        keys = []
        # first we'll sort the keys beacuse, well, reasons
        for key in self.options.keys():
            keys.append(key)
        keys.sort()
        for key in keys:
            options.append(self.get_opt(key))
        return options


    def keys(self) -> list:
        ''':return: list[str]'''
        return [key for key in self.options.keys()]


    # Option utility
    def get_missing_options(self) -> list:
        '''Returns names of options which are required but do not have values designated
        :return: list<str> Indicating names of required options missing values'''
        missing = []
        for option in self.get_all():
            if (option.is_required and (option.value == None)):
                missing.append(option.name)
        return missing


    def validate_options(self) -> tuple:
        '''Checks all options for validity
        :rtype: <tuple<bool, str | None>> Validity of options, error message OR None'''
        for option in self.get_all():
            valid, msg = option.validate()
            if not valid:
                return (valid, msg)
        return (True, None)


    def show_options(self, mask: bool = False, truncate: bool = True) -> list:
        '''Returns options and information for the module. This need not be overriden by child classes
        :return: list[list[str]]'''
        rows = []
        max_val_chars = 56 if truncate else 999999999 # Show maz of 56 chars if truncation enabled (else 1B chars)

        for opt in self.get_all():
            required = 'True' if opt._is_required else 'False'

            org = opt.masked() if (mask and opt._sensitive) else opt.str_val() 
            value = org if (len(org) < max_val_chars) else f'{org[0:25]}.....{org[-25:]}'

            rows.append([opt._name, value, required, opt._desc])

        return rows


    # Set / unset option functionality
    def set_opt(self, name: str, value: str) -> bool:
        # Mostly from @zeroSteiner in Termineter
        '''Set the value for an existing option; Does nothing if name doesn't exist
        :param str name: Name of the option to set
        :param str value: Value to set. Casted from str to the option's type.'''
        option = self.get_opt(name)
        if option == None:
            return False # option not found
        
        if option._opt_type == 'str': # String or readable file
            option._value = value

        elif option._opt_type == 'bool': # Boolean
            if value.lower() in ['true', '1', 'on']:
                option._value = True
            elif value.lower() in ['false', '0', 'off']:
                option._value = False
            else: # Invalid
                raise TypeError(f'Invalid value \'{value}\' for boolean option \'{name}\'')
        
        elif option._opt_type == 'int': # Integers
            if (not value.isdigit()):
                raise TypeError(f'Invalid value \'{value}\' for integer option \'{name}\'')
            else:
                option._value = int(value)

        elif option._opt_type == 'flt':
            if ((value.count('.') > 1) or (not value.replace('.', '').isdigit())): # Too many decimals or contains non-digit characters
                raise TypeError(f'Invalid value \'{value}\' for float option \'{name}\'')
            else:
                option._value = float(value)

        else: # Non supported option type
            raise StratustrykeException(f'Unsupported option type \'{option._opt_type}\' for option \'{name}\'')

        return True # successfuly updated


    def unset_opt(self, name: str) -> None:
        '''Unsets the specified option's value'''
        opt = self.get_opt(name)
        if opt != None:
            opt.unset()


    def reset_opt(self, name: str) -> None:
        '''Sets option's current value to the default value'''
        opt = self.get_opt(name)
        opt.reset()


    # Add options functionality
    def add_string(self, name: str, desc: str, required: bool = False, default: str = None, regex: str = '', sensitive: bool = False) -> None:
        '''Add string option to Options container
        :param str name: Name of option to add
        :param str desc: Description / help message for the option
        :param str default: Initial starting value
        :param bool required: Whether this is a required option
        :param str regex: If regex pattern can be used for validation, regex pattern to match during validation'''
        name = name.upper()
        self.options.update({name: Option(name, 'str', desc, required, default, regex, sensitive)})

    def add_integer(self, name: str, desc: str, required: bool = False, default: int = None) -> None:
        '''Add an integer option to Options container
        :param str name: Name of the option to add
        :param str desc: Description / help statement associated with the option
        :param int default: Initial starting value
        :param bool required: Whether this is required for the module or not'''
        name = name.upper()
        self.options[name] = Option(name, 'int', desc, required, default)

    def add_float(self, name: str, desc: str, required: bool = False, default: float = None) -> None:
        '''Add float option to container
        :param str name: Name of option to add
        :param str desc: Description / help statement
        :param float default: Initial starting value
        :param bool required: Whether option is required for the module or not'''
        name = name.upper()
        self.options[name] = Option(name, 'flt', desc, required, default)

    def add_boolean(self, name: str, desc: str, required: bool = False, default: bool = None) -> None:
        '''Add boolean option to container
        :param str name: Name of option to add
        :param str desc: Description / help statement
        :param bool default: Initial starting value
        :param bool required: Whether option is required for the module or not'''
        name = name.upper()
        self.options[name] = Option(name, 'bool', desc, required, default)

# End class Options
