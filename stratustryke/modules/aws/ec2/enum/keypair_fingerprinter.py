
import base64
import hashlib

from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519

from stratustryke.core.module.aws import AWSModule


class Module(AWSModule):

    OPT_PRIVATE_KEY = 'PRIVATE_KEY'
    OPT_KEY_PASSWORD = 'KEY_PASSWORD'


    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Identify EC2 instances configured with given SSH key(s)',
            'Details': 'Computes various SSH key fingerprints and identifies EC2 keypairs / instances matching the key fingerprint',
            'References': ['']
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


    def parse_provided_keys(self) -> list[str]:
        '''Returns a list[str] containing each key's text value'''
        opt = self.get_opt_multiline(Module.OPT_PRIVATE_KEY)
        password = self.get_opt(Module.OPT_KEY_PASSWORD)
        verbose_output = self.get_opt(Module.OPT_VERBOSE)

        ret = []
 
        if len(opt) == 1: # Either a file or a directory
            provided_path = Path(opt[0])

            # Either path doesn't exist or was invalid input
            if not provided_path.exists():
                self.print_error(f'{Module.OPT_PRIVATE_KEY} path does not exist or is invalid : {provided_path[0]}')
                return []
            

            # Provided a single path to a key file or a directory            
            if provided_path.is_file(): key_paths = [provided_path]
            else: key_paths = [f for f in provided_path.iterdir() if f.is_file()] # Any files in the directory

            for keyfile in key_paths:
                try:
                    with open(keyfile, 'r') as f: keytext = f.read()
                    ret.append(self.load_private_key_from_pem(keytext, password))
                except Exception as err:
                    self.print_failure(f'Could not load key file {keyfile}')
                    if verbose_output: self.print_failure(str(err))


        else: # A pasted key
            keytext = '\n'.join(opt)

            try:
                ret.append(self.load_private_key_from_pem(keytext, password))
            except Exception as err:
                # self.print_failure(f'Could not load key text: {keytext.replace("\n", "\\n")}')
                if verbose_output: self.print_failure(str(err))
        return ret


    def calculate_fingerprints(self, key) -> dict:
        '''Calculate each of the fingerprints for a given key'''
        fingerprints = []
        # SHA1 PCKS#8 - for RSA keys generated by AWS
        try:
            aws_rsa_sha1 = self.aws_rsa_style_sha1_pkcs8_private(key)
            fingerprints.append(aws_rsa_sha1)
            if self.verbose: self.print_status(f'SHA1 PKCS#8 (AWS Generated RSA): {aws_rsa_sha1}')

        except Exception as e:
            self.log_warning(f'Unable to calculate SHA1 PKCS#8')
            if self.verbose:
                self.print_warning(f'Unable to calculate SHA1 PKCS#8: {e}')


        #  MD5 of public key DER SPKI - for imported keys
        try:
            md5_spki = self.imported_key_md5_spki_public(key)
            fingerprints.append(md5_spki)
            if self.verbose: self.print_status(f'MD5 SPKI (Imported Key Fingerprint): {md5_spki}')

        except Exception as e:
            self.log_warning(f'Unable to calculate MD5 of key DER SPKKI')
            if self.verbose:
                self.print_warning(f'Unable to calculate MD5 of key DER SPKKI: {e}')

        # OpenSSH SHA-256 - Ed25519 / general OpenSSH keys
        try:
            sha256_ssh = self.openssh_sha256_fingerprint(key)
            fingerprints.append(sha256_ssh)
            if self.verbose: self.print_status(f'OpenSSH SHA-256 (AWS Generated ED25519): {md5_spki}')

        except Exception as e:
            self.log_warning(f'Unable to calculate SHA-256 of key')
            if self.verbose:
                self.print_warning(f'Unable to calculate SHA-256: {e}')

        return fingerprints
    

    def get_regional_keypair_fingerprints(self, region: str, keypairs: dict) -> int:
        '''Return the number of key pairs found in a region and accumulate keypair fingerprints in keypairs param'''

        cred = self.get_cred()

        try:
            client = cred.session(region).client('ec2')
            
            # Apparently describe_key_pairs does not paginate 
            # API response structure: {'Keypairs: [{{'KeyPairId': str, 'KeyType': str, 'Tags': array, 'CreateTime': datetime, 'KeyName':  str, 'KeyFingerprint': str}]}
            res = client.describe_key_pairs()
            pairs = res.get('KeyPairs', [])

            for entry in pairs:
                key_name = entry.get('KeyName', None)
                fingerprint = entry.get('KeyFingerprint')
                if fingerprint in keypairs.keys():
                    keypairs[fingerprint][region] = key_name
                else:
                    keypairs[fingerprint] = {region: key_name}

            if self.verbose:
                self.print_status(f'Found {len(pairs)} key pairs in region {region}')

        except Exception as err:
            self.print_error(f'Error performing ec2:DescribeKeyPairs in {region}')
            if self.verbose:
                self.print_error(str(err))

        # Ret structure {'Fingerprint': {'region1': 'keyname', 'region2': 'keyname'},}
        return None


    def run(self) -> None:
        keys = self.parse_provided_keys()

        regions = self.get_regions()

        # TODO DESCRIBE_KEYPAIRS_HERE
        
        key_fingerprints = []
        key_count = 0
        # Calculate key fingerprints
        for i, key_text in enumerate(keys):
            try:
                key_fingerprints = self.calculate_fingerprints(key_text)
                if len(key_fingerprints) < 1:
                    self.print_warning(f'Unable to calculate any fingerprints for key {i+1}! Skipping...')
                    continue

                key_count += 1
            
            except Exception as err:
                self.print_warning(f'Error calculating fingerprint for key {i+1}')
                if self.verbose:
                    self.print_warning(str(err))

        # No valid keys provided (future proofing for directory support)   
        if key_count < 1:
            self.print_error(f'Unable to compute fingerprint for provided key(s)')
            return None
        
        self.print_status(f'Calculated fingerprint(s) for {key_count} keys')


        # Check if keys exist in EC2 that match the fingerprint
        deployed_keypairs = {}
        for region in regions:
            self.get_regional_keypair_fingerprints(region, deployed_keypairs)
            
        self.print_status(f'Identified {len(deployed_keypairs.keys())} total unique keypairs within the account')


        # now match on our fingerprints
        found_keypairs = {}
        for fingerprint in key_fingerprints:
            if fingerprint in deployed_keypairs.keys():
                # Exists in the account
                matched_regions = [str(region) for region in deployed_keypairs[fingerprint].keys()]
                self.print_success(f'{fingerprint} match found in {",".join(matched_regions)}')
                found_keypairs[fingerprint] = matched_regions


        # Search ec2 instances within matched regions for the key
        for key, regions in found_keypairs.items():
            self.check_ec2_instances_for_keypair(region, key)
            # ec2:DescribeInstances (paginated) to determine if an instance was run with that key fingerprint (might need to match on the key name)


        print(deployed_keypairs)
        
