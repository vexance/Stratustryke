# Helper functions related to parsing EC2 resources / data
#

from stratustryke.lib.exception import StratustrykeException

def format_sg_rules(self, ruleset: list[dict]) -> list[str]:
    '''Format raw rule data into a more readable line
    :param ruleset: list[dict] IP permissions response from ec2:DescribeSecurityGroup
    :rtype: list[str] lines containing human-readable ACL descriptions
    '''
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
        raise StratustrykeException(str(err))

    return lines