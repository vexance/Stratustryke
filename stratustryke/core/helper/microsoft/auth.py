#!/usr/bin/env python3
import argparse
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional

import requests
import jwt  # pip install pyjwt
import base64
import json

AZ_AUTH_BASE = 'https://login.microsoftonline.com'
MGMT_RESOURCE = 'https://management.azure.com'

# Common delegated scopes
COMMON_SCOPES = 'offline_access openid profile'

# Resource-specific /.default scopes
AZ_MGMT_SCOPE = f'https://management.azure.com/.default {COMMON_SCOPES}'
GRAPH_SCOPE = f'https://graph.microsoft.com/.default {COMMON_SCOPES}'

DEFAULT_RESOURCE_SCOPES: Dict[str, str] = {
    'arm': AZ_MGMT_SCOPE,
    'graph': GRAPH_SCOPE,
}

# Default public client ID (Azure CLI)
DEFAULT_PUBLIC_CLIENT_ID = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'


# ---------------------------------------------------------------------------
# Device code helpers (interactive)
# ---------------------------------------------------------------------------

def get_org_openid_config():
    '''
    GET /organizations/v2.0/.well-known/openid-configuration
    '''
    url = f'{AZ_AUTH_BASE}/organizations/v2.0/.well-known/openid-configuration'
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


def request_device_code(client_id: str, scope: str):
    '''
    POST /organizations/oauth2/v2.0/devicecode
    '''
    url = f'{AZ_AUTH_BASE}/organizations/oauth2/v2.0/devicecode'
    data = {
        'client_id': client_id,
        'scope': scope,
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()


def poll_device_token(
    client_id: str,
    device_code: str,
    interval: int = 5,
    timeout: int = 600,
):
    '''
    POST /organizations/oauth2/v2.0/token (polling)
    '''
    url = f'{AZ_AUTH_BASE}/organizations/oauth2/v2.0/token'
    data = {
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
        'client_id': client_id,
        'device_code': device_code,
    }

    start = time.time()
    while True:
        resp = requests.post(url, data=data)

        if resp.status_code == 200:
            return resp.json()

        try:
            body = resp.json()
        except ValueError:
            resp.raise_for_status()

        error = body.get('error')
        if error in ('authorization_pending', 'slow_down'):
            if error == 'slow_down':
                interval += 5
            if time.time() - start > timeout:
                raise RuntimeError('Timed out waiting for user to complete device code authentication.')
            time.sleep(interval)
            continue
        elif error == 'expired_token':
            raise RuntimeError('Device code expired before user completed authentication.')
        else:
            raise RuntimeError(f'Token polling failed: {body}')


# ---------------------------------------------------------------------------
# Refresh-token -> multi-resource tokens helpers (interactive path)
# ---------------------------------------------------------------------------

def refresh_access_token(
    tenant_id: str,
    client_id: str,
    refresh_token: str,
    scope: str,
    client_secret: Optional[str] = None,
):
    '''
    Exchange a refresh token for a new access token for a single resource (scope)
    using the v2.0 token endpoint.
    '''
    url = f'{AZ_AUTH_BASE}/{tenant_id}/oauth2/v2.0/token'

    data = {
        'client_id': client_id,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'scope': scope,
    }
    if client_secret:
        data['client_secret'] = client_secret

    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()


def get_tokens_for_resources(
    tenant_id: str,
    client_id: str,
    refresh_token: str,
    resource_scopes: Optional[Dict[str, str]] = None,
    client_secret: Optional[str] = None,
) -> Dict[str, dict]:
    '''
    Use a single refresh token to obtain multiple access tokens for different resources.
    '''
    if resource_scopes is None:
        resource_scopes = DEFAULT_RESOURCE_SCOPES

    tokens_by_resource: Dict[str, dict] = {}
    current_refresh = refresh_token

    for name, scope in resource_scopes.items():
        token_response = refresh_access_token(
            tenant_id=tenant_id,
            client_id=client_id,
            refresh_token=current_refresh,
            scope=scope,
            client_secret=client_secret,
        )
        tokens_by_resource[name] = token_response

        new_rt = token_response.get('refresh_token')
        if new_rt:
            current_refresh = new_rt

    return tokens_by_resource


# ---------------------------------------------------------------------------
# Service principal helpers (client secret or certificate)
# ---------------------------------------------------------------------------

def build_client_assertion(tenant_id: str, client_id: str, private_key_pem: str) -> str:
    '''
    Build a JWT client assertion for certificate-based auth.
    '''
    token_endpoint = f'{AZ_AUTH_BASE}/{tenant_id}/oauth2/v2.0/token'
    now = datetime.utcnow()
    payload = {
        'aud': token_endpoint,
        'iss': client_id,
        'sub': client_id,
        'jti': str(uuid.uuid4()),
        'nbf': int(now.timestamp()),
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=10)).timestamp()),
    }

    assertion = jwt.encode(payload, private_key_pem, algorithm='RS256')
    if isinstance(assertion, bytes):
        assertion = assertion.decode('utf-8')
    return assertion


def client_credentials_token(
    tenant_id: str,
    client_id: str,
    secret_or_cert: str,
    scope: str,
    use_cert: bool,
):
    '''
    Get a token using client_credentials, either with a client secret or a certificate (private key).
    '''
    url = f'{AZ_AUTH_BASE}/{tenant_id}/oauth2/v2.0/token'

    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'scope': scope,
    }

    if use_cert:
        with open(secret_or_cert, 'r', encoding='utf-8') as f:
            private_key_pem = f.read()
        assertion = build_client_assertion(tenant_id, client_id, private_key_pem)
        data['client_assertion_type'] = (
            'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
        )
        data['client_assertion'] = assertion
    else:
        data['client_secret'] = secret_or_cert

    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()


def get_sp_tokens_for_resources(
    tenant_id: str,
    client_id: str,
    secret_or_cert: str,
    resource_scopes: Optional[Dict[str, str]] = None,
    use_cert: bool = False,
) -> Dict[str, dict]:
    '''
    Use service principal credentials (secret or cert) to obtain tokens for resources.
    '''
    if resource_scopes is None:
        resource_scopes = DEFAULT_RESOURCE_SCOPES

    tokens_by_resource: Dict[str, dict] = {}

    for name, scope in resource_scopes.items():
        token_response = client_credentials_token(
            tenant_id=tenant_id,
            client_id=client_id,
            secret_or_cert=secret_or_cert,
            scope=scope,
            use_cert=use_cert,
        )
        tokens_by_resource[name] = token_response

    return tokens_by_resource



def decode_jwt_no_verify(token: str) -> dict:
    '''
    Decodes a JWT without verifying the signature.
    We only need to inspect the payload (claims).
    '''
    # JWT format: header.payload.signature
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError('Invalid JWT format')

    payload_b64 = parts[1]
    # Pad the Base64 URL string
    padding = '=' * (-len(payload_b64) % 4)
    payload_b64 += padding
    payload_json = base64.urlsafe_b64decode(payload_b64.encode('utf-8'))
    return json.loads(payload_json)


def describe_identity_from_claims(claims: dict) -> str:
    '''
    Determine whether this token belongs to a user or service principal
    and return a formatted string.

    User tokens:
        - use 'upn' or 'preferred_username'
        - object id: 'oid'

    Service Principal tokens:
        - name: 'azp' or 'appid'
        - object id: 'oid'
    '''

    oid = claims.get('oid') or 'unknown-oid'

    # Heuristic indicators of a USER:
    upn = claims.get('upn') or claims.get('preferred_username')
    if upn:
        return f'{upn} ({oid})'

    # Otherwise assume SERVICE PRINCIPAL
    name = claims.get('azp') or claims.get('appid') or 'UnknownServicePrincipal'
    return f'{name} ({oid})'

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_bool(s: str) -> bool:
    return s.lower() in ('1', 'true', 'yes', 'y', 'on')


def main():
    parser = argparse.ArgumentParser(
        description='Azure auth demo: interactive device code or service principal (secret/cert).'
    )
    parser.add_argument(
        '--interactive',
        type=parse_bool,
        default=True,
        help='Use interactive device-code login (default: true). '
             'If --service-principal is provided, that takes precedence.',
    )
    parser.add_argument(
        '--tenant',
        type=str,
        help='Tenant ID (GUID or domain). '
             'Defaults to \'organizations\' for interactive; REQUIRED for service principal.',
    )
    parser.add_argument(
        '--service-principal',
        type=str,
        help='Service principal application (client) ID for SP auth. '
             'If set, service principal auth is used.',
    )
    parser.add_argument(
        '--secret',
        type=str,
        help='Client secret OR path to a PEM certificate/private-key file for SP auth.',
    )
    parser.add_argument(
        '--client-id',
        type=str,
        default=DEFAULT_PUBLIC_CLIENT_ID,
        help=f'Client ID for interactive device-code login (default: {DEFAULT_PUBLIC_CLIENT_ID}).',
    )

    args = parser.parse_args()

    # Decide mode
    use_sp = args.service_principal is not None

    # Determine tenant
    if use_sp:
        if not args.tenant:
            raise SystemExit('--tenant is required when using --service-principal.')
        tenant_id = args.tenant
    else:
        tenant_id = args.tenant or 'organizations'

    if use_sp:
        # -------------------------------------------------------------------
        # Service principal auth (client_credentials)
        # -------------------------------------------------------------------
        if not args.secret:
            raise SystemExit('--secret is required for service principal auth '
                             '(client secret or path to cert/private key).')

        sp_client_id = args.service_principal

        use_cert = os.path.exists(args.secret)
        if use_cert:
            print(f'Using certificate/private key from: {args.secret}')
        else:
            print('Using client secret for service principal authentication.')

        tokens_by_resource = get_sp_tokens_for_resources(
            tenant_id=tenant_id,
            client_id=sp_client_id,
            secret_or_cert=args.secret,
            use_cert=use_cert,
        )

    else:
        # -------------------------------------------------------------------
        # Interactive device-code auth
        # -------------------------------------------------------------------
        client_id = args.client_id

        if tenant_id == 'organizations':
            org_config = get_org_openid_config()
            print(f'Issuer for \'organizations\': {org_config.get("issuer")}\n')

        device = request_device_code(client_id, AZ_MGMT_SCOPE)
        print('To sign in, use a browser to open:')
        print(device['verification_uri'])
        print('and enter the code:')
        print(device['user_code'])
        print()

        token_response = poll_device_token(
            client_id,
            device['device_code'],
            interval=device.get('interval', 5),
        )

        refresh_token = token_response.get('refresh_token')
        if not refresh_token:
            raise RuntimeError('No refresh_token returned; ensure \'offline_access\' is in the scope.')

        print('Initial device-code flow completed.')
        print('Got refresh token (length):', len(refresh_token))

        tokens_by_resource = get_tokens_for_resources(
            tenant_id=tenant_id,
            client_id=client_id,
            refresh_token=refresh_token,
        )

    # -----------------------------------------------------------------------
    # Common output: print first 40 chars of ARM & Graph tokens
    # -----------------------------------------------------------------------
    arm_access_token = tokens_by_resource['arm']['access_token']
    graph_access_token = tokens_by_resource['graph']['access_token']

    print('\nARM access token (first 40 chars):   ', arm_access_token[:40])
    print('Graph access token (first 40 chars): ', graph_access_token[:40])


    # -----------------------------------------------------------------------
    # Decode JWT to identify who/what is logged in
    # -----------------------------------------------------------------------
    print('\n=== Identity Information (from ARM token) ===')

    try:
        arm_claims = decode_jwt_no_verify(arm_access_token)
        identity_str = describe_identity_from_claims(arm_claims)
        print('Logged in as:', identity_str)
    except Exception as e:
        print('Could not decode identity from token:', e)


if __name__ == '__main__':
    main()
