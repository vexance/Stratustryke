
* aws/s3/enum/resource_account_id
    * Multi-bucket/object support and swap to S3 URI input format

* aws/cloudformation/privesc/create_backdoor_role
* aws/lambda/privesc/create_func_role_creds
* aws/ecr/enum/registry_inspector
* aws/ec2/enum/ip_address_collector
    * aws/multi/enum/ip_address_collector
* aws/ssm/enum/run_command_history
* aws/sagemaker/enum/model_artifact_inspector
* aws/ecs/enum/task_env_variable_collector
* aws/dynamodb/enum/table_secret_scanner
* aws/bedrock/enum/inference_prompt_inspector
* aws/cloudfront/enum/function_src_extractor
* aws/appconfig/enum/config_variable_collector

* azure/entra/enum/password_policy_inspector
* azure/entra/enum/dynamic_membership_analyzer
* azure/entra/util/create_guest_invitation

* azure/keyvault/exfil/dump_vault_contents
* azure/appconfig/exfil/dump_config_store
* azure/acr/enum/registry_inspector
* azure/vms/enum/ip_address_collector

* GCP AuthN