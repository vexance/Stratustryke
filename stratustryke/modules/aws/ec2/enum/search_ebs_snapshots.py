
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

    def run(self):
        cred = self.get_cred()
        target = self.get_opt(Module.OPT_TARGET_ACCOUNT_ID)

        self.framework.print_status(f'Filtering ec2:DescribeSnapshots on owner-id: {target}')
        snapshots = []
        try:
            session = cred.session()
            client = session.client('ec2')

            res = client.describe_snapshots(Filters=[{
                'Name': 'owner-id',
                'Values': [f'{target}']
            }])
            snapshots.extend(res.get('Snapshots', []))
            pagination_token = res.get('NextToken', None)

            while pagination_token != None:
                res = client.describe_snapshots(NextToken=pagination_token, Filters=[{
                    'Name': 'owner-id',
                    'Values': [f'{target}']
                }])
                snapshots.extend(res.get('Snapshots', []))
                pagination_token = res.get('NextToken', None)

        except Exception as err:
            self.framework.print_failure(f'{err}')

        if len(snapshots) < 1:
            self.framework.print_status(f'No public EBS snapshots found.')

        for snap in snapshots:
            enc = 'Encrypted' if (snap.get('Encrypted', False)) else 'Unencrypted'
            snap_id = snap.get('SnapshotId', None)
            size = snap.get('VolumeSize', -1)
            desc = snap.get('Description', '')

            if (snap_id != None):
                self.framework.print_success(f'{enc} snapshot: {snap_id} ({size} GiB) - {desc}')
        
        return