config = {
    'region': 'us-west-1',
    'account_production': '585222078325',  # lattice-prod
    'ami_id_production': 'ami-0a8fedc00cfa35c4a', # latest checkfiles AMI 
    'portal_secrets_arn_production': 'arn:aws:secretsmanager:us-west-1:585222078325:secret:checkfiles-portal-secret-5A1cNL',
    'slack_channel_id_arn': 'arn:aws:secretsmanager:us-west-1:585222078325:secret:slack-channel-id-lWBvOZ',
    'slack_token_arn': 'arn:aws:secretsmanager:us-west-1:585222078325:secret:bot-token-Z0jak9',
    'instance_name_production': 'checkfiles',
    'instance_profile_arn_production': 'arn:aws:iam::585222078325:instance-profile/checkfiles-instance',
    'instance_security_group_production': 'sg-0da14ac5025210cf9',
    'checkfiles_tag_production': 'cdk-step-function',
}