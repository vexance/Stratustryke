# Just some thin wrappers for custom exception types 
#

from stratustryke.lib import StratustrykeException


class FrameworkConfigurationError(StratustrykeException):
	pass

class FrameworkRuntimeError(StratustrykeException):
	pass