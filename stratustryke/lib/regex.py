
from re import compile

##### AWS Related Regex Patterns #####
AWS_ANY_ARN_REGEX = compile(r'(\"|\\s)(arn:aws:[a-z0-9]+:[a-z0-9\\-]*:(|[0-9]{12}):[^\\s\"]+)(\"|\\s)')

AWS_ROLE_ARN_REGEX = compile(r'arn:aws:iam::[0-9]{12}:role/.*')

AWS_PRINCIPAL_ARN_REGEX = compile(
    r'^arn:(?P<partition>aws[a-zA-Z-]*)?:iam::'
    r'(?P<account_id>\d{12}):'
    r'(?:(?P<principal_type>role|user|federated)/(?P<name>[A-Za-z0-9+=,.@_\-\/]+)|root)$'
)

AWS_SERVICE_PRINCIPAL_REGEX = compile(
    r'^(?P<service>[a-z0-9-]+(\.[a-z0-9-]+)*)\.amazonaws\.com(\.cn)?$'
)

AWS_ACCESS_KEY_REGEX = r'(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}'
AWS_SECRET_KEY_REGEX = r'[0-9a-zA-Z\\/+]{40}'
AWS_SESSION_TOKEN_REGEX = r'[0-9a-zA-Z\\/+]{364}'
AWS_ACCOUNT_ID_REGEX = compile(r'[0-9]{12}')

##### Microsoft Related Regex Patterns #####
UUID_LOWERCASE_REGEX = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
