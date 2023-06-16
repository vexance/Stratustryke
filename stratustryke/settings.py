# Author: @vexance
# Purpose: Overall program configuration settings
# 

import os, sys
from pathlib import Path

frozen = getattr(sys, 'frozen', False)

# Determine what platform we're running on. 
on_linux = sys.platform.startswith('linux')
on_windows = sys.platform.startswith('win')

py_v2 = sys.version_info[0] == 2
py_v3 = sys.version_info[0] == 3

# Default framework configuration settings
AWS_DEFAULT_REGION = 'us-east-1'
MASK_SENSITIVE_OPTIONS = True
COLORED_OUTPUT = True
FORCE_VALIDATE_OPTIONS = False
SPOOL_OVERWRITE = False
DEFAULT_TABLE_FORMAT = 'simple' # list of options available at https://pypi.org/project/tabulate/
DEFAULT_WORKSPACE = 'default'
FIREPROX_CRED_ALIAS = 'fireprox'