

##### AWS Related Regex Patterns #####
AWS_ANY_ARN_REGEX = r'(\"|\\s)(arn:aws:[a-z0-9]+:[a-z0-9\\-]*:(|[0-9]{12}):[^\\s\"]+)(\"|\\s)'
AWS_ROLE_ARN_REGEX = r'arn:aws:iam::[0-9]{12}:role/.*'
AWS_ACCESS_KEY_REGEX = r'(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}'
AWS_SECRET_KEY_REGEX = r'[0-9a-zA-Z\\/+]{40}'
AWS_SESSION_TOKEN_REGEX = r'[0-9a-zA-Z\\/+]{364}'
AWS_ACCOUNT_ID_REGEX = r'[0-9]{12}'

##### Microsoft Related Regex Patterns #####
UUID_LOWERCASE_REGEX = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
