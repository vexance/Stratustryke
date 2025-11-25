# Author: @vexance
# Purpose: Overall program configuration settings
# 

import sys

frozen = getattr(sys, 'frozen', False)

# Determine what platform we're running on. 
on_linux = sys.platform.startswith('linux') or sys.platform.startswith('darwin') # Linux / Mac
on_windows = sys.platform.startswith('win') # Windows

py_v2 = sys.version_info[0] == 2
py_v3 = sys.version_info[0] == 3


AWS_DEFAULT_ENABLED_REGIONS = [
    'us-east-1',
    'us-east-2',
    'us-west-1',
    'us-west-2',
    'ap-south-1',
    'ap-northeast-3',
    'ap-northeast-2',
    'ap-southeast-1',
    'ap-southeast-2',
    'ap-northeast-1',
    'ca-central-1',
    'eu-central-1',
    'eu-west-1',
    'eu-west-2',
    'eu-west-3',
    'eu-north-1',
    'sa-east-1'
]

AWS_DISABLED_REGIONS = [
    'af-south-1',
    'ap-east-1',
    'ap-east-2',
    'ap-south-2',
    'ap-southeast-3',
    'ap-southeast-4',
    'ap-southeast-5',
    'ap-southeast-6',
    'ap-southeast-7',
    'ca-west-1',
    'eu-central-2',
    'eu-south-1',
    'eu-south-2',
    'il-central-1',
    'me-central-1',
    'me-south-1',
    'mx-central-1'
]

AWS_ALL_REGIONS = AWS_DEFAULT_ENABLED_REGIONS + AWS_DISABLED_REGIONS


# Default framework configuration settings
AWS_DEFAULT_REGION = '__DEFAULT__' # __DEFAULT__ will indicate running in all default regions
AWS_SINGULAR_DEFAULT_REGION = 'us-east-1' # used if a module doesn't have multi-region support
AZURE_DEFAULT_SUBS = '__DEFAULT__' # __DEFAULT__ will result in attempting to list all subscriptions the principal can access
GCP_DEFAULT_PROJECTS = '__DEFAULT__' # __DEFAULT__ will attempt to list projects the principal can access

MASK_SENSITIVE_OPTIONS = True
COLORED_OUTPUT = True
FORCE_VALIDATE_OPTIONS = False
SPOOL_OVERWRITE = False
TRUNCATE_OPTIONS = True
DEFAULT_TABLE_FORMAT = 'simple' # list of options available at https://pypi.org/project/tabulate/
DEFAULT_WORKSPACE = 'default'
FIREPROX_CRED_ALIAS = 'fireprox'
STRATUSTRYKE_LOGLEVEL = 'INFO' # Must be in enum set: DEBUG, INFO, WARNING, ERROR, CRITICAL
HTTP_VERIFY_SSL = False
HTTP_STSK_HEADER = True