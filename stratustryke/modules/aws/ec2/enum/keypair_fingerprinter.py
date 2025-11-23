
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
    OPT_RESOLVE_SGS = 'RESOLVE_SG_RULES'


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

        self._advanced.add_boolean(Module.OPT_RESOLVE_SGS, 'When enabled & verbose, check inbound rules for security groups', False, False)


    @property
    def search_name(self):
        return f'aws/ec2/enum/{self.name}'
    

    def colon_hex(self, digest_bytes: bytes) -> str:
        '''aabbcc... => aa:bb:cc...'''
        hexstr = digest_bytes.hex()
        return ':'.join(hexstr[i:i+2] for i in range(0, len(hexstr), 2))


    def load_private_key_from_pem(self, pem_text: str, key_pwd: str):
        '''Load RSA / Ed25519 private key from key material text with hazmat'''
        return serialization.load_pem_private_key(pem_text.encode('utf-8'), password=key_pwd)
        

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
        # Format: b'ssh-xxx AAAAB3NzaC1yc2EAAAADAQABAAABAQ... [comment]'
        parts = openssh_pub.split()
        if len(parts) < 2:
            raise ValueError('Unexpected OpenSSH public key format')
        blob_b64 = parts[1]
        blob = base64.b64decode(blob_b64)
        digest = hashlib.sha256(blob).digest()
        b64 = base64.b64encode(digest).decode('ascii').rstrip('=')  # ssh-keygen style (no padding)
        return f'SHA256:{b64}'


    def detect_key_type(self, key) -> str:
        '''Return key type RSA|ED25516|UNKNOWN'''
        if isinstance(key, rsa.RSAPrivateKey): return 'RSA'
        if isinstance(key, ed25519.Ed25519PrivateKey): return 'ED25519'
        return 'UNKNOWN'


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
    

    def get_regional_keypair_fingerprints(self, region: str, accumulator: dict) -> int:
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
                fingerprint = entry.get('KeyFingerprint', None)

                if fingerprint in accumulator.keys():
                    accumulator[fingerprint][region] = key_name
                else:
                    accumulator[fingerprint] = {region: key_name}

            if self.verbose:
                self.print_status(f'Found {len(pairs)} key pairs in region {region}')

        except Exception as err:
            self.print_error(f'Error performing ec2:DescribeKeyPairs in {region}')
            if self.verbose:
                self.print_error(str(err))

        # Ret structure {'aa:bb:cc:dd:ee:ff:11:22': {'region1': 'keyname', 'region2': 'keyname'},}
        return None
    

    def match_fingerprints(self, key_fingerprints: str, deployed_keypairs: dict) -> dict:
        '''Restructure data to annotate matching keys for inspected regions'''
        found_keypairs = {}
        
        for fingerprint in key_fingerprints:
            
            # Exists in the account within any region
            if fingerprint in deployed_keypairs.keys():
                for region, keyname in deployed_keypairs[fingerprint].items():

                    if region not in found_keypairs.keys(): found_keypairs[region] = {}
                
                    self.print_warning(f'({keyname}) matched in {region} against {fingerprint}')
                    found_keypairs[region][keyname] = fingerprint
        
        return found_keypairs


    def get_instance_ips(self, instance: dict) -> list[str]:
        '''Return all unique IP address for an instance's network interfaces / IP associations'''
        ips = []
        try:
            # Top-level IPv4/IPv6
            ips.append(instance.get('PrivateIpAddress', None))
            ips.append(instance.get('PublicIpAddress', None))
            ips.append(instance.get('Ipv6Address', None))

            # Walk network interfaces
            for ni in instance.get('NetworkInterfaces', []) or []:
                # Interface primary private IP
                ips.append(ni.get('PrivateIpAddress', None))

                # Interface association-level addresses
                assoc = ni.get('Association', {}) or {}
                ips.append(assoc.get('PublicIp', None))
                ips.append(assoc.get('CarrierIp', None))
                ips.append(assoc.get('CustomerOwnedIp', None))
                # Any explicitly listed private IPs (and their associations)
                for pip in ni.get('PrivateIpAddresses', []) or []:
                    ips.append(pip.get('PrivateIpAddress', None))
                    
                    private_assoc = pip.get('Association', {}) or {}
                    ips.append(private_assoc.get('PublicIp', None))
                    ips.append(private_assoc.get('CarrierIp', None))
                    ips.append(private_assoc.get('CustomerOwnedIp', None))

                # IPv6 addresses on the interface
                for ipv6 in ni.get('Ipv6Addresses', []) or []:
                    ips.append(ipv6.get('Ipv6Address', None))

        except Exception as err:
            self.print_failure(f'Failed to retrieve instance IP addresses')
            if self.verbose:
                self.print_error(str(err))
        
        # Unique and remove None values
        uniqued = set(ips)
        uniqued.discard(None)
        return list(uniqued)


    def format_sg_rules(self, ruleset: list[dict]) -> list[str]:
        '''Format raw rule data into a more readable line'''
        lines = []

        try:

            for perm in ruleset:
                proto = perm.get('IpProtocol', '-1')
                if proto == '-1':
                    proto_str = 'all protocols'
                else:
                    proto_str = proto

                from_port = perm.get('FromPort')
                to_port = perm.get('ToPort')

                if from_port is None or to_port is None:
                    port_str = 'all ports'
                elif from_port == to_port:
                    port_str = f'port {from_port}'
                else:
                    port_str = f'ports {from_port}-{to_port}'

                # Collect all sources (IPv4, IPv6, SGs, prefix lists)
                sources = []

                for r in perm.get('IpRanges', []):
                    cidr = r.get('CidrIp')
                    desc = r.get('Description')
                    if cidr and desc:
                        sources.append(f'{cidr} ({desc})')
                    elif cidr:
                        sources.append(cidr)

                for r in perm.get('Ipv6Ranges', []):
                    cidr = r.get('CidrIpv6')
                    desc = r.get('Description')
                    if cidr and desc:
                        sources.append(f'{cidr} ({desc})')
                    elif cidr:
                        sources.append(cidr)

                for g in perm.get('UserIdGroupPairs', []):
                    gid = g.get('GroupId')
                    gname = g.get('GroupName')
                    desc = g.get('Description')
                    label_parts = []
                    if gname:
                        label_parts.append(gname)
                    if gid:
                        label_parts.append(gid)
                    base = ' / '.join(label_parts) if label_parts else '(security-group)'
                    if desc:
                        sources.append(f'SG {base} ({desc})')
                    else:
                        sources.append(f'SG {base}')

                for p in perm.get('PrefixListIds', []):
                    plid = p.get('PrefixListId')
                    desc = p.get('Description')
                    if plid and desc:
                        sources.append(f'PrefixList {plid} ({desc})')
                    elif plid:
                        sources.append(f'PrefixList {plid}')

                if not sources:
                    sources_str = 'from <no sources>'
                else:
                    sources_str = 'from ' + ', '.join(sources)

                # e.g., Allow tcp on port 22 from 0.0.0.0/0
                line = f'Allow {proto_str} on {port_str} {sources_str}'
                lines.append(line)
        except Exception as err:
            self.print_failure(f'Failed to resolve security group info')
            if self.verbose:
                self.print_error(str(err))

        return lines


    def get_inbound_sg_rules(self, region: str, groups: list[str]) -> list[str]:
        '''Resolve security group IP rules'''
        if groups == []: return []
        
        cred = self.get_cred()

        try:
            client = cred.session(region).client('ec2')
            res = client.describe_security_groups(GroupIds=groups)

            sgs = res.get('SecurityGroups', [])
            rules = []
            for sg in sgs:
                rules.extend(sg.get('IpPermissions', []))

            return self.format_sg_rules(rules)
        except Exception as err:
            self.print_failure(f'Exception thrown performing ec2:DescribeSecurityGroups on {",".join(groups)}')
            if self.verbose:
                self.print_error(str(err))
            return []


    def check_ec2_instances_for_keypair(self, region: str, keynames: list) -> list[dict]:
        '''Return ARNs of instances configured with the provided key fingerprint'''
        cred = self.get_cred()
        # Get account ID (for building ARNs)

        instances = []
        try:
            client = cred.session(region).client('ec2')
            paginator = client.get_paginator('describe_instances')

            for page in paginator.paginate():
                for reservation in page.get('Reservations', []):
                    for inst in reservation.get('Instances', []):
                        # Key pair
                        key_name = inst.get('KeyName', None)
                        if key_name not in keynames: continue

                        # If it is in keynames, we have a match!
                        instance_id = inst.get('InstanceId', None)
                        instance_arn = f'arn:aws:ec2:{region}:{cred.account_id}:instance/{instance_id}'
                        instance_profile = inst.get('IamInstanceProfile', {}).get('Arn', None)
                        instance_state = inst.get('State', {}).get('Name', 'unknown')
                        instance_platform = inst.get('Platform', 'Linux') # 'Windows' or None as per docs
                        ip_addresses = self.get_instance_ips(inst)
                        instance_sgs = [sg.get('GroupId', None) for sg in inst.get('SecurityGroups', []) or []]
                        instance_info = {
                            'KeyName': key_name,
                            'InstanceId': instance_id,
                            'InstanceArn': instance_arn,
                            'InstanceProfile': instance_profile,
                            'IpAddresses': ip_addresses,
                            'InstanceState': instance_state,
                            'InstancePlatform': instance_platform,
                            'InstanceSecurityGroups': instance_sgs
                        }

                        instances.append(instance_info)

        except Exception as err:
            self.print_failure(f'Exception thrown when performing ec2:DescribeInstances in region {region}')
            if self.verbose:
                self.print_error(str(err))
            return []
    

        return instances


    def report_instance_match(self, inst: dict) -> None:
        '''Prints info regarding the matched instance'''
        inst_key = inst.get('KeyName')
        inst_arn = inst.get('InstanceArn')
        inst_id = inst.get('InstanceId')
        inst_state = inst.get('InstanceState')
        inst_platform = inst.get('InstancePlatform')
        inst_ips = inst.get('IpAddresses')
        inst_profile = inst.get('InstanceProfile')
        inst_sgs = inst.get('InstanceSecurityGroups')
            

        self.print_success(f'Keypair match found ({inst_key}): {inst_arn}')
        if self.verbose:
            self.print_success(f'({inst_id}) Instance state: {inst_state}')
            self.print_success(f'({inst_id}) Instance platform: {inst_platform}')
            self.print_success(f'({inst_id}) IAM instance profile: {inst_profile}')
            self.print_success(f'({inst_id}) IP addresses: {", ".join(inst_ips)}')
            self.print_success(f'({inst_id}) Security groups: {", ".join(inst_sgs)}')

            if self.get_opt(Module.OPT_RESOLVE_SGS):
                # arn:aws:ec2:<region>:<account>:instance/<instance-id>
                region = inst_arn.split(':')[3]
                rule_info = self.get_inbound_sg_rules(region, inst_sgs)
                if len(rule_info) > 0:
                    for line in rule_info:
                        self.print_line(f'    ({inst_id}) {line}')
                else:
                    self.print_warning(f'({inst_id}) No rules found or error encountered when inspecting security groups')


    def run(self) -> None:
        keys = self.parse_provided_keys()
        regions = self.get_regions()
        
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
        
        self.print_status(f'Calculated fingerprint(s) for {key_count} key(s)')


        # Check if keys exist in EC2 that match the fingerprint
        deployed_keypairs = {}
        for region in regions:
            self.get_regional_keypair_fingerprints(region, deployed_keypairs)
            
        self.print_status(f'Identified {len(deployed_keypairs.keys())} total unique keypairs within the account')


        matches = self.match_fingerprints(key_fingerprints, deployed_keypairs)
        

        # Search ec2 instances within matched regions for the key
        for region, keypair in matches.items():
            key_names = matches[region].keys()
            matched_instances = self.check_ec2_instances_for_keypair(region, key_names)

            if len(matched_instances) > 0:
                for inst in matched_instances:
                    self.report_instance_match(inst)

            else:
                self.print_failure(f'No matching instances found within region {region}')

            # ec2:DescribeInstances (paginated) to determine if an instance was run with that key fingerprint (might need to match on the key name)

        
