
from stratustryke.core.module.aws import AWSModule
from pathlib import Path

class Module(AWSModule):

    OPT_TARGET_ACCOUNT_ID = 'ACCOUNT_ID'

    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Identify public EBS snapshots associated with a provided AWS account id',
            'Details': 'Performs an ec2:DescribeSnapshots call to identify public EBS snapshots and filters output based on the provided account id.',
            'References': [
                'https://hackingthe.cloud/aws/enumeration/loot_public_ebs_snapshots/',
                'https://github.com/BishopFox/dufflebag'
            ]
        }
        self._options.add_string(Module.OPT_TARGET_ACCOUNT_ID, 'Target account ID to filter public snapshots on', True, regex='^[0-9]{12}$')


    @property
    def search_name(self):
        return f'aws/ec2/enum/{self.name}'
    

    def search_for_public_snapshots(self, region: str, target: list[str]) -> list:
        '''ec2:DescribeSnapshots in a region filtering on the owner-id as the target'''
        snapshots = []
        try:
            client = self.get_cred.session(region).client('ec2')

            paginator = client.get_paginator('describe_snapshots')
            pages = paginator.paginate(Filters=[{
                'Name': 'owner-id',
                'Values': target
            }])

            for page in pages: snapshots.extend(page.get('Snapshots', []))

        except Exception as err:
            self.print_failure(f'Failed to perform ec2:DescribeSnapshots in {region}')
            if self.verbose: self.print_error(str(err))

        return snapshots


    def run(self):

        targets = self.get_opt_multiline(Module.OPT_TARGET_ACCOUNT_ID)
        regions = self.get_regions()

        self.print_status(f'Searching for snapshots with owner ids: {targets}')
        for region in regions:
            if self.verbose: self.print_status(f'Filtering ec2:DescribeSnapshots in {region} on target owners')
            
            snapshots = self.search_for_public_snapshots(region, targets)

            snapshot_count = len(snapshots)
            if snapshot_count < 1:
                self.print_warning(f'No snapshots found in {region} for account(s) {", ".join(targets)}')
                continue

            for snap in snapshots:
                enc = 'Encrypted' if (snap.get('Encrypted', False)) else 'Unencrypted'
                snap_id = snap.get('SnapshotId', None)
                owner_id = snap.get('OwnerId', 'UNKNOWN')
                size = snap.get('VolumeSize', -1)
                desc = snap.get('Description', '')
                snap_arn = f'arn:aws:ec2:{region}:{owner_id}:snapshot/{snap_id}'

            if (snap_id != None):
                self.print_success(f'({size} GiB | {enc}) {snap_arn}')
                if desc != '': self.print_success(f'({snap_id}) Description: {desc}')
        
        return

