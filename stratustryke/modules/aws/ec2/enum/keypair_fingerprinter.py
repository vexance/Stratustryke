
import base64
import hashlib
import sys
import json

from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption,
)
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519

from stratustryke.core.module import AWSModule
from stratustryke.core.lib import StratustrykeException


class Module(AWSModule):

    OPT_PRIVATE_KEY = 'PRIVATE_KEY'
    OPT_KEY_PASSWORD = 'KEY_PASSWORD'


    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Identify EC2 instances configured with given SSH key(s)',
            'Details': 'Computes various SSH key fingerprints and identifies EC2 keypairs / instances matching the key fingerprint',
            'References': []
        }

        self._options.add_string(Module.OPT_PRIVATE_KEY, 'Private SSH to match against resources (f/d/p)', True)
        self._options.add_string(Module.OPT_KEY_PASSWORD, 'Password to use when loading private key(s)', False)


    @property
    def search_name(self):
        return f'aws/ec2/enum/{self.name}'
    

    def colon_hex(self, digest_bytes: bytes) -> str:
        '''aabbcc... => aa:bb:cc...'''
        hexstr = digest_bytes.hex()
        return ":".join(hexstr[i:i+2] for i in range(0, len(hexstr), 2))


    def load_private_key_from_pem(self, pem_text: str, key_pwd: str):
        '''Load RSA / Ed25519 private key from key material text with hazmat'''
        return serialization.load_pem_private_key(pem_text.encode("utf-8"), password=key_pwd)
        

    def aws_rsa_style_sha1_pkcs8_private(self, key) -> str:
        '''SHA-1 of DER-encoded PKCS#8 private key'''
        der = key.private_bytes(encoding=Encoding.DER, format=PrivateFormat.PKCS8, encryption_algorithm=NoEncryption())
        return self.colon_hex(hashlib.sha1(der).digest())


    def imported_key_md5_spki_public(self, key) -> str:
        '''MD5 of DER-encoded SPKI / public key.'''
        pub = key.public_key()
        spki_der = pub.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        return self.colon_hex(hashlib.md5(spki_der).digest())


    def openssh_sha256_fingerprint(self, key) -> str:
        '''SHA-256 of public key blob; base64 w/ no padding.'''
        pub = key.public_key()
        openssh_pub = pub.public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH)
        # Format: b"ssh-xxx AAAAB3NzaC1yc2EAAAADAQABAAABAQ... [comment]"
        parts = openssh_pub.split()
        if len(parts) < 2:
            raise ValueError("Unexpected OpenSSH public key format")
        blob_b64 = parts[1]
        blob = base64.b64decode(blob_b64)
        digest = hashlib.sha256(blob).digest()
        b64 = base64.b64encode(digest).decode("ascii").rstrip("=")  # ssh-keygen style (no padding)
        return f"SHA256:{b64}"


    def detect_key_type(self, key) -> str:
        '''Return key type RSA|ED25516|UNKNOWN'''
        if isinstance(key, rsa.RSAPrivateKey): return "RSA"
        if isinstance(key, ed25519.Ed25519PrivateKey): return "ED25519"
        return "UNKNOWN"


    def parse_provided_keys(self) -> list:
        opt = self.get_opt_multiline(Module.OPT_PRIVATE_KEY)
        password = self.get_opt(Module.OPT_KEY_PASSWORD)
        verbose_output = self.get_opt(Module.OPT_VERBOSE)

        ret = []

        if len(opt) == 1: # Either a file or a directory
            provided_path = Path(opt[0])

            # Either path doesn't exist or was invalid input
            if not provided_path.exists():
                self.framework.print_error(f'{Module.OPT_PRIVATE_KEY} path does not exist or is invalid : {provided_path[0]}')
                return []
            

            # Provided a single path to a key file or a directory            
            if provided_path.is_file(): key_paths = [provided_path]
            else: key_paths = [f for f in provided_path.iterdir() if f.is_file()] # Any files in the directory

            for keyfile in key_paths:
                try:
                    with open(keyfile, 'r') as f: keytext = f.read()
                    ret.append(self.load_private_key_from_pem(keytext, password))
                except Exception as err:
                    self.framework.print_failure(f'Could not load key file {keyfile}')
                    if verbose_output: self.framework.print_failure(str(err))


        else: # A pasted key
            keytext = '\n'.join(opt)
            ret.append(self.load_private_key_from_pem(keytext, password))
            try:
                ret.append(self.load_private_key_from_pem(keytext, password))
            except Exception as err:
                self.framework.print_failure(f'Could not load key text: {keytext.replace('\n', '\\n')}')
                if verbose_output: self.framework.print_failure(str(err))

        return ret


    def calculate_fingerprints(self, key) -> dict:
        '''Calculate each of the fingerprints for a given key'''
        fingerprints = {}
        # SHA1 PCKS#8 - for RSA keys generated by AWS
        try:
            aws_rsa_sha1 = self.aws_rsa_style_sha1_pkcs8_private(key)
            fingerprints['AWS_RSA_SHA1'] = aws_rsa_sha1

        except Exception as e:
            fingerprints['AWS_RSA_SHA1'] = None


        #  MD5 of public key DER SPKI - for imported keys
        try:
            md5_spki = self.imported_key_md5_spki_public(key)
            fingerprints['IMPORTED_MD5'] = md5_spki

        except Exception as e:
            fingerprints['IMPORTED_MD5'] = None


        # OpenSSH SHA-256 - Ed25519 / general OpenSSH keys
        try:
            sha256_ssh = self.openssh_sha256_fingerprint(key)
            fingerprints['OpenSSH_SHA-256'] = sha256_ssh

        except Exception as e:
            fingerprints['OpenSSH_SHA-256'] = None

        return fingerprints
    

    def get_regional_keypair_fingerprints(self)
        '''Return '''



    def run(self) -> None:
        cred = self.get_cred()
        keys = self.parse_provided_keys()
        regions = self.get_opt(Module.OPT_AWS_REGION)

        # TODO DESCRIBE_KEYPAIRS_HERE

        regional_keypairs = self.get_regional_keypair_fingerprints()


        
        
