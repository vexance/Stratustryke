from stratustryke.core.module import AWSModule
from stratustryke.core.lib import StratustrykeException, module_data_dir
from pathlib import Path
from time import sleep

class Module(AWSModule):
    def __init__(self, framework) -> None:
        super().__init__(framework)
        self._info = {
            'Authors': ['@vexance'],
            'Description': 'Downloads a public EBS snapshot to disk',
            'Details': 'Leverages ec2:CopySnapshot, ec2:DescribeSnapshots, ebs:ListSnapshotBlocks, and ebs:GetSnapshotBlock to copy a public EBS snapshot, then list and retrieve all blocks of data stored in it. Direct EBS API pricing will impose costs of roughly of $0.01 per 1.5 GB',
            'References': ['https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.copy_snapshot']
        }

        self._options.add_string('SNAPSHOT_ID', 'Id of the snapshot to obtain a copy of', True)
        self._options.get_opt('AWS_REGION')._desc = 'Region containing the target snapshot'
        self._options.add_string('DEST_REGION', 'Destination region to copy the snapshot to', True, self._options.get_val('AWS_REGION'))
        self._options.add_string('DESCRIPTION', 'Description to apply to the new snapshot copy', False, 'Stratustryke')
        self._options.add_string('OUTFILE', 'Name of output file to copy the snapshot as', False)
        self._options.add_string('DOWNLOAD_DIR', 'Directory to save the snapshot copy to', False, module_data_dir(self.name))


    def validate_options(self) -> tuple:
        valid, msg = super().validate_options()
        if not valid:
            return (False, msg)

        download_dir = self.get_opt('DOWNLOAD_DIR')
        download_dir = Path(download_dir).resolve().absolute()
        if not (download_dir.exists() and download_dir.is_dir()):
            return (False, f'Download directory does not exist: {download_dir}')

        return (True, None)


    @property
    def search_name(self):
        return f'aws/util/{self.name}'


    def copy_ebs_snapshot(self, desc: str, src_id: str, src_reg: str, dest: str) -> str | None:
        '''Queue the copy of a snapshot in AWS (ec2:CopySnapshot), return ID of the copy or NoneType'''
        cred = self.get_cred()
        try:
            session = cred.session(region=src_reg)
            client = session.client('ec2')
            res = client.copy_snapshot(Description=desc, SourceSnapshotId=src_id, SourceRegion=src_reg, DestinationRegion=dest)

            copy_id = res.get('SnapshotId', False)
            if not copy_id:
                raise StratustrykeException('Unable to retrieve ID of the snaphshot copy.')

        except Exception as err:
            self.framework.print_failure(f'{err}')
            return None
            
        return copy_id


    def verify_copy_completion(self, copy_id: str, src_id: str) -> bool | None:
        '''Perform ec2:DescribeSnapshots until response comes back with state 'completed' '''
        cred = self.get_cred()
        try:
            session = cred.session()
            client = session.client('ec2')
            state = 'pending'

            while state == 'pending':
                res = client.describe_snapshots(SnapshotIds=[copy_id])

                state = res.get('Snapshots', [])[0].get('State', 'Unknown')

                if state not in ['pending', 'completed']:
                    raise StratustrykeException(f'Unexpected snapshot state for {copy_id}: {state}')

                if state == 'pending':
                    self.framework.print_status(f'{copy_id} is in state \'{state}\', sleeping 15 seconds')
                    sleep(15)        
                
        except Exception as err:
            self.framework.print_error(f'{err}')
            return None

        return True


    def list_blocks(self, copy_id: str) -> list | None:
        '''Obtain list of snapshot block indices and block tokens via ebs:ListSnapshotBlocks'''
        cred = self.get_cred()
        blocks = []

        try:
            session = cred.session()
            client = session.client('ebs')
            res = client.list_snapshot_blocks(SnapshotId=copy_id)
            
            blocks.extend(res.get('Blocks', []))
            token = res.get('NextToken', False)

            while token:
                res = client.list_snapshot_blocks(SnapshotId=copy_id)
                blocks.extend(res.get('Blocks', []))
                token = res.get('NextToken', False)

        except Exception as err:
            self.framework.print_failure(f'{err}')
            return None

        return blocks


    def export_snapshot(self, copy_id: str, out: Path, blocks: list) -> bool | None:
        '''Download each block from a snapshot via ebs:GetSnapshotBlock'''
        cred = self.get_cred()

        try:
            session = cred.session()
            client = session.client('ebs')

            i = 0
            for block in blocks:
                index = block.get('BlockIndex', None)
                token = block.get('BlockToken', None)

                if (index == None) or (token == None):
                    print(block)
                    raise StratustrykeException(f'Invalid block index or token at block {i}: Index: {index}; Token: {token}')
                
                res = client.get_snapshot_block(SnapshotId=copy_id, BlockIndex=index, BlockToken=token)

                body = res.get('BlockData', None)
                if body == None:
                    raise StratustrykeException(f'No block data found for block {i}')

                with open(out, 'ab') as file:
                    file.write(body.read())

                i += 1

        except Exception as err:
            self.framework.print_failure(f'{err}')
            return None

        return True


    def cleanup(self, copy_id: str) -> bool | None:
        '''Remove copy of original snapshot with ec2:DeleteSnapshot'''
        # Delete the copy of the snapshot
        cred = self.get_cred()
        try:
            session = cred.session()
            client = session.client('ec2')
            res = client.delete_snapshot(SnapshotId=copy_id)

        except Exception as err:
            self.framework.print_failure(f'{err}')
            return None
        
        return True


    def run(self):
        snap_id = self.get_opt('SNAPSHOT_ID')
        src_region = self.get_opt('AWS_REGION')
        dest_region = self.get_opt('DEST_REGION')
        desc = self.get_opt('DESCRIPTION')
        download_dir = self.get_opt('DOWNLOAD_DIR')
        outfile = self.get_opt('OUTFILE')

        copy_id = self.copy_ebs_snapshot(desc, snap_id, src_region, dest_region)
        if copy_id == None:
            return

        self.framework.print_success(f'Queued copy of snapshot \'{snap_id}\' as \'{copy_id}\', sleeping 15 seconds')
        sleep(15)
        self.framework.print_status('Verifying completion state...')


        # Wait for the snapshot copy to complete
        is_complete = self.verify_copy_completion(copy_id, snap_id)
        if is_complete == None:
            return

        self.framework.print_status(f'Completed copy of original snapshot {snap_id}')
        self.framework.print_status(f'Listing blocks for snapshot: {copy_id}')
        
        blocks = self.list_blocks(copy_id)
        if blocks == None:
            return

        self.framework.print_status(f'Copying {len(blocks)} snapshot blocks to disk...')
        
        # Get path to output file
        if outfile == None:
            self.framework.print_status(f'Outfile not specified, defaulting to {download_dir}/{snap_id}.ebs')
            outfile = Path(download_dir/f'copy_{snap_id}.ebs')
        else:
            outfile = Path(download_dir/outfile)

        is_complete = self.export_snapshot(copy_id, outfile, blocks)
        if is_complete == None:
            return

        self.framework.print_success(f'Saved {snap_id} as \'{Path(download_dir)/outfile}\'')
        self.framework.print_status(f'Queueing deletion of snapshot copy...')

        is_complete = self.cleanup(copy_id)
        if is_complete == None:
            self.framework.print_error(f'Could not remove snapshot {copy_id}; be sure to delete this manually via AWS console')
            return

        self.framework.print_success(f'Deleted snapshot: {copy_id}')

        return

