#!/usr/bin/python
from __future__ import absolute_import
from __future__ import unicode_literals

import argparse
import logging
import os
import sys

from stratustryke import __version__
from stratustryke.core.interface import InteractiveInterpreter


def main():
	parser = argparse.ArgumentParser(description='Straustryke: modular cloud security framework', conflict_handler='resolve')
	parser.add_argument('-v', '--version', action='version', version=parser.prog + ' Version: ' + __version__)
	parser.add_argument('--log-level', dest='loglvl', action='store', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], default='CRITICAL', help='set the logging level')
	parser.add_argument('--rc-file', dest='resource_file', default=None, help='execute a resource file')
	arguments = parser.parse_args()

	logging.getLogger('').setLevel(logging.DEBUG)
	console_log_handler = logging.StreamHandler()
	console_log_handler.setLevel(getattr(logging, arguments.loglvl))
	console_log_handler.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
	logging.getLogger('').addHandler(console_log_handler)
	rc_file = arguments.resource_file
	del arguments, parser

	interpreter = InteractiveInterpreter(rc_file=rc_file, log_handler=console_log_handler)
	interpreter.cmdloop()
	logging.shutdown()

if __name__ == '__main__':
	main()

	