from dataclasses import dataclass


from aws_cdk import Duration
from aws_cdk import Environment
from aws_cdk import Stack

from aws_cdk.aws_lambda_python_alpha import PythonFunction
from aws_cdk.aws_lambda import Runtime

from aws_cdk.aws_iam import PolicyStatement
from aws_cdk.aws_iam import Role

from constructs import Construct

from aws_cdk.aws_events import Rule
from aws_cdk.aws_events import Schedule

from aws_cdk.aws_events_targets import SfnStateMachine

from aws_cdk.aws_secretsmanager import Secret as SMSecret

from aws_cdk.aws_stepfunctions import Choice
from aws_cdk.aws_stepfunctions import Condition
from aws_cdk.aws_stepfunctions import JsonPath
from aws_cdk.aws_stepfunctions import Pass
from aws_cdk.aws_stepfunctions import Succeed
from aws_cdk.aws_stepfunctions import StateMachine
from aws_cdk.aws_stepfunctions import TaskInput
from aws_cdk.aws_stepfunctions import Wait
from aws_cdk.aws_stepfunctions import WaitTime

from aws_cdk.aws_stepfunctions_tasks import CallAwsService
from aws_cdk.aws_stepfunctions_tasks import EventBridgePutEvents
from aws_cdk.aws_stepfunctions_tasks import EventBridgePutEventsEntry
from aws_cdk.aws_stepfunctions_tasks import LambdaInvoke

from typing import Any


@dataclass
class RunCheckfilesStepFunctionProps:
    ami_id: str
    instance_name: str
    instance_profile_arn: str
    instance_security_group_id: str
    checkfiles_tag: str
    portal_secrets_arn: str
    slack_channel_id_arn: str 
    slack_token_arn: str 
    s3_bucket_name: str

class RunCheckfilesStepFunction(Stack):

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            *,
            props: RunCheckfilesStepFunctionProps,
            **kwargs: Any
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.props = props

        self.portal_secrets = SMSecret.from_secret_complete_arn(
            self,
            id='PortalSecrets',
            secret_complete_arn=self.props.portal_secrets_arn
        )

        make_checkfiles_started_message = Pass(
            self,
            'MakeCheckfilesStartedMessage',
            parameters={
                'detailType': 'CheckfilesStarted',
                'source': 'RunCheckfilesStepFunction',
                'detail': {
                    'metadata': {
                        'includes_slack_notification': True
                    },
                    'data': {
                        'slack': {
                            'text': JsonPath.format(
                                ':rocket: *EC2 Instance checkfiles {} started* | Preparing for {} pending files.',
                                JsonPath.string_at('$.instance_name_suffix'),
                                JsonPath.string_at('$.number_of_files_pending')
                            )
                        }
                    }
                },
                'files_pending.$': '$.files_pending',
                'number_of_files_pending.$': '$.number_of_files_pending',
                'instance_name_suffix.$': '$.instance_name_suffix',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                'update.$': '$.update',
            },
        )

        make_pending_files_checked_message = Pass(
            self,
            'MakePendingFilesCheckedMessage',
            parameters={
                'detailType': 'PendingFilesChecked',
                'source': 'RunCheckfilesStepFunction',
                'detail': {
                    'metadata': {
                        'includes_slack_notification': True
                    },
                    'data': {
                        'slack': {
                            'text': JsonPath.format(
                                ':white_check_mark: *Checkfiles {} in progress* | Found {} files in upload_status: pending',
                                JsonPath.string_at('$.instance_name_suffix'),
                                JsonPath.string_at('$.number_of_files_pending')
                            )
                        }
                    }
                },
                'files_pending.$': '$.files_pending',
                'number_of_files_pending.$': '$.number_of_files_pending',
                'instance_name_suffix.$': '$.instance_name_suffix',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                'update.$': '$.update',
            },
        )

        make_checkfiles_finished_message = Pass(
            self,
            'MakeCheckfilesFinishedMessage',
            parameters={
                'detailType': 'CheckfilesFinished',
                'source': 'RunCheckfilesStepFunction',
                'detail': {
                    'metadata': {
                        'includes_slack_notification': True
                    },
                    'data': {
                        'slack': {
                            'text': JsonPath.format(
                                ':white_check_mark: *Checkfiles {} finished* | command_status: {} | See log group checkfiles-log for details',
                                JsonPath.string_at('$.instance_name_suffix'),
                                JsonPath.string_at('$.checkfiles_command_status')
                            )
                        }
                    }
                },
                'instance_id.$': '$.instance_id',
                'instance_id_list.$': '$.instance_id_list',
                'number_of_files_pending.$': '$.number_of_files_pending',
                'instance_name_suffix.$': '$.instance_name_suffix',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                'update.$': '$.update',
                'command_id.$': '$.command_id',
                'checkfiles_command_status.$': '$.checkfiles_command_status'
            },
        )
        

        make_progress_message = Pass(
            self,
            'MakeProgressMessage',
            parameters={
                'detailType': 'CheckfilesProgress',
                'source': 'RunCheckfilesStepFunction',
                'detail': {
                    'metadata': {
                        'includes_slack_notification': True
                    },
                    'data': {
                        'slack': {
                            'text': JsonPath.format(
                                ':hourglass_flowing_sand: *Checkfiles {} Progress* | Status: {} | Processed {} out of {} files.',
                                JsonPath.string_at('$.instance_name_suffix'),
                                JsonPath.string_at('$.checkfiles_command_status'),
                                JsonPath.string_at('$.line_count'),
                                JsonPath.string_at('$.number_of_files_pending')
                            )
                        }
                    }
                },
                'checkfiles_command_status.$': '$.checkfiles_command_status',
                'instance_id.$': '$.instance_id',
                'command_id.$': '$.command_id',
                'instance_id_list.$': '$.instance_id_list',
                'in_progress.$': '$.in_progress',
                'iterator.$': '$.iterator',
                'line_count.$': '$.line_count',
                'number_of_files_pending.$': '$.number_of_files_pending',
                'instance_name_suffix.$': '$.instance_name_suffix',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                'update.$': '$.update'
            }
        )

        get_checkfiles_command_status_lambda = PythonFunction(
            self,
            'GetCheckfilesCommandStatusLambda',
            entry='checkfiles_runner/lambdas/get_status',
            runtime=Runtime.PYTHON_3_11,
            index='main.py',
            handler='get_checkfiles_command_status',
            timeout=Duration.seconds(180),
        )

        get_checkfiles_command_status_lambda.add_to_role_policy(
            PolicyStatement(
                actions=[
                    'ssm:GetCommandInvocation',
                    'ssm:SendCommand' 
                ],
                resources=['*'],
            )
        )


        get_checkfiles_command_status = LambdaInvoke(
            self,
            'GetCheckfilesCommandStatus',
            lambda_function=get_checkfiles_command_status_lambda,
            payload=TaskInput.from_object({
                "command_id.$": "$.command_id",
                "instance_id.$": "$.instance_id",
                "instance_name_suffix.$": "$.instance_name_suffix",
                "number_of_files_pending.$": "$.number_of_files_pending",
                "backend_uri.$": "$.backend_uri",
                "query.$": "$.query",
                "update.$": "$.update",
                "iterator.$": "$.iterator"
            }),
            payload_response_only=True,
            result_selector={
                'checkfiles_command_status.$': '$.checkfiles_command_status',
                'instance_id.$': '$.instance_id',
                'command_id.$': '$.command_id',
                'line_count.$': '$.line_count', 
                'instance_id_list.$': '$.instance_id_list',
                'in_progress.$': '$.in_progress',
                'iterator.$': '$.iterator',
                'number_of_files_pending.$': '$.number_of_files_pending',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                'update.$': '$.update',
                'instance_name_suffix.$': '$.instance_name_suffix'
            }
        )
        
        check_pending_files_lambda = PythonFunction(
            self,
            'CheckPendingFilesLambda',
            entry='checkfiles_runner/lambdas/check_pending',
            runtime=Runtime.PYTHON_3_11,
            index='main.py',
            handler='check_pending_files',
            timeout=Duration.seconds(30),
            environment={
                'PORTAL_SECRETS_ARN': self.props.portal_secrets_arn,
            }
        )

        self.portal_secrets.grant_read(check_pending_files_lambda)

        check_pending_files = LambdaInvoke(
            self,
            'CheckPendingFiles',
            lambda_function=check_pending_files_lambda,
            payload=TaskInput.from_object({
                "query.$": "$.query",
                "instance_name_suffix.$": "$.instance_name_suffix",
                "backend_uri.$": "$.backend_uri",
                "update.$": "$.update"
            }),
            payload_response_only=True,
            result_selector={
                'files_pending.$': '$.files_pending',
                'number_of_files_pending.$': '$.number_of_files_pending',
                'instance_name_suffix.$': '$.instance_name_suffix',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                "update.$": "$.update"
            }
        )

        initialize_counter = Pass(
            self,
            'InitializeCounter',
            parameters={
                'iterator': {'index': 0, 'step': 1, 'count': 144, 'continue': True},
                'number_of_files_pending.$': '$.number_of_files_pending',
                'instance_name_suffix.$': '$.instance_name_suffix',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                'update.$': '$.update',
            }
        )

        increment_counter_lambda = PythonFunction(
            self,
            'IncrementCounterLambda',
            entry='checkfiles_runner/lambdas/counter',
            runtime=Runtime.PYTHON_3_11,
            index='increment.py',
            handler='increment_counter',
            timeout=Duration.seconds(60),
        )

        increment_counter = LambdaInvoke(
            self,
            'IncrementCounter',
            lambda_function=increment_counter_lambda,
            payload=TaskInput.from_object({
                "iterator.$": "$.iterator",
                "instance_id.$": "$.instance_id",
                "command_id.$": "$.command_id",
                "instance_name_suffix.$": "$.instance_name_suffix",
                "backend_uri.$": "$.backend_uri",
                "query.$": "$.query",
                "update.$": "$.update",
                "number_of_files_pending.$": "$.number_of_files_pending"
            }),
            payload_response_only=True,
            result_selector={
                'iterator.$': '$.iterator',
                'instance_id.$': '$.instance_id',
                'command_id.$': '$.command_id',
                'instance_name_suffix.$': '$.instance_name_suffix',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                'update.$': '$.update',
                'number_of_files_pending.$': '$.number_of_files_pending'
            }
        )

        create_checkfiles_instance_lambda = PythonFunction(
            self,
            'CreateCheckfilesInstanceLambda',
            entry='checkfiles_runner/lambdas/create_instance',
            runtime=Runtime.PYTHON_3_11,
            index='main.py',
            handler='create_checkfiles_instance',
            timeout=Duration.seconds(360),
            environment={
                'AMI_ID': self.props.ami_id,
                'INSTANCE_NAME': self.props.instance_name,
                'INSTANCE_PROFILE_ARN': self.props.instance_profile_arn,
                'SECURITY_GROUP': self.props.instance_security_group_id,
                'CHECKFILES_TAG': self.props.checkfiles_tag,
            }
        )

        create_checkfiles_instance_lambda.add_to_role_policy(
            PolicyStatement(
                actions=[
                    'iam:PassRole',
                ],
                resources=['*'],
            )
        )

        create_checkfiles_instance_lambda.add_to_role_policy(
            PolicyStatement(
                actions=[
                    'ec2:RunInstances',
                    'ec2:AssociateIamInstanceProfile',
                    'ec2:ModifyInstanceAttribute',
                    'ec2:CreateVolume',
                    'ec2:AttachVolume',
                    'ec2:CreateTags',
                    'ec2:DescribeInstances',
                    'ec2:ReportInstanceStatus',
                ],
                resources=['*'],
            )
        )

        create_checkfiles_instance = LambdaInvoke(
            self,
            'CreateCheckfilesInstance',
            lambda_function=create_checkfiles_instance_lambda,
            payload=TaskInput.from_object({
                "instance_name_suffix.$": "$.instance_name_suffix",
                "number_of_files_pending.$": "$.number_of_files_pending",
                "iterator.$": "$.iterator",
                "backend_uri.$": "$.backend_uri",
                "query.$": "$.query",
                "update.$": "$.update"
            }),
            payload_response_only=True,
            result_selector={
                'instance_id.$': '$.instance_id',
                'instance_type.$': '$.instance_type',
                'iterator.$': '$.iterator',
                'instance_name_suffix.$': '$.instance_name_suffix',
                'number_of_files_pending.$': '$.number_of_files_pending',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                'update.$': '$.update'
            }
        )

        wait_instance_ssm_registration = Wait(
            self,
            'WaitForSSMReg',
            time=WaitTime.duration(
                Duration.minutes(2)
            )
        )

        run_checkfiles_command_lambda = PythonFunction(
            self,
            'RunCheckfilesCommandLambda',
            entry='checkfiles_runner/lambdas/run_checkfiles',
            runtime=Runtime.PYTHON_3_11,
            index='main.py',
            handler='run_checkfiles_command',
            timeout=Duration.seconds(60),
            environment={
                'PORTAL_SECRETS_ARN': self.props.portal_secrets_arn,
            }
        )

        self.portal_secrets.grant_read(run_checkfiles_command_lambda)

        run_checkfiles_command_lambda.add_to_role_policy(
            PolicyStatement(
                actions=[
                    'ssm:SendCommand',
                    'ssm:GetCommandInvocation',
                ],
                resources=['*'],
            )
        )

        run_checkfiles_command = LambdaInvoke(
            self,
            'RunCheckFilesCommand',
            lambda_function=run_checkfiles_command_lambda,
            payload=TaskInput.from_object({
                "instance_id.$": "$.instance_id",
                "instance_name_suffix.$": "$.instance_name_suffix",
                "number_of_files_pending.$": "$.number_of_files_pending",
                "backend_uri.$": "$.backend_uri",
                "query.$": "$.query",
                "update.$": "$.update",
                "iterator.$": "$.iterator"
            }),
            payload_response_only=True,
            result_selector={
                'instance_id.$': '$.instance_id',
                'command_id.$': '$.command_id',
                'iterator.$': '$.iterator',
                'instance_name_suffix.$': '$.instance_name_suffix',
                'number_of_files_pending.$': '$.number_of_files_pending',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                'update.$': '$.update'
            }
        )

        send_progress_notification = self.make_slack_notification_task(
            'SendProgressSlackNotification'
        )

        upload_report_lambda = PythonFunction(
            self,
            'UploadReportLambda',
            entry='checkfiles_runner/lambdas/upload_report',
            runtime=Runtime.PYTHON_3_11,
            index='main.py',
            handler='upload_report_to_slack',
            timeout=Duration.seconds(300),
            environment={
                'PORTAL_SECRETS_ARN': self.props.portal_secrets_arn,
                'SLACK_TOKEN_ARN': self.props.slack_token_arn,
                'SLACK_CHANNEL_ID_ARN': self.props.slack_channel_id_arn,
                'S3_BUCKET_NAME': self.props.s3_bucket_name
            }
        )
        slack_token_secret = SMSecret.from_secret_complete_arn(
            self,
            'SlackTokenSecret',
            secret_complete_arn=self.props.slack_token_arn
        )
        slack_channel_secret = SMSecret.from_secret_complete_arn(
            self,
            'SlackChannelSecret',
            secret_complete_arn=self.props.slack_channel_id_arn
        )

        slack_token_secret.grant_read(upload_report_lambda)
        slack_channel_secret.grant_read(upload_report_lambda)
        self.portal_secrets.grant_read(upload_report_lambda)

        upload_report_lambda.add_to_role_policy(
            PolicyStatement(
                actions=[
                    'ssm:SendCommand',
                    'ssm:GetCommandInvocation'
                ],
                resources=['*'],
            )
        )

        upload_report_lambda.add_to_role_policy(
            PolicyStatement(
                actions=[
                    's3:PutObject'
                ],
                resources=[f'arn:aws:s3:::{self.props.s3_bucket_name}/*'],
            )
        )

        upload_report = LambdaInvoke(  # This is the LambdaInvoke task
            self,
            'UploadReport',
            lambda_function=upload_report_lambda,
            payload=TaskInput.from_object({
                "instance_id.$": "$.instance_id",
                "instance_name_suffix.$": "$.instance_name_suffix",
                "instance_id_list.$": "$.instance_id_list",
                "backend_uri.$": "$.backend_uri",
                "query.$": "$.query",
                "update.$": "$.update"
            }),
            payload_response_only=True,
            result_selector={
                'status.$': '$.status',
                'instance_id.$': '$.instance_id',
                'instance_id_list.$': '$.instance_id_list',
                'instance_name_suffix.$': '$.instance_name_suffix',
                'backend_uri.$': '$.backend_uri',
                'query.$': '$.query',
                'update.$': '$.update'
            }
        )

        no_files_to_process = Succeed(
            self,
            'No files to process.'
        )

        terminate_instance = CallAwsService(
            self,
            'TerminateInstance',
            service='ec2',
            action='terminateInstances',
            iam_resources=['*'],
            parameters={
                'InstanceIds.$': '$.instance_id_list'
            },
            result_path=JsonPath.DISCARD,
        )

        wait_for_sixty_minutes = Wait(
            self,
            'WaitSixtyMinutes',
            time=WaitTime.duration(
                Duration.minutes(60)
            )
        )

        wait_for_five_minutes = Wait(
            self,
            'WaitTenMinutes',
            time=WaitTime.duration(
                Duration.minutes(5)
            )
        )

        send_checkfiles_started_notification = self.make_slack_notification_task(
            'SendCheckfilesStartedSlackNotification')
        send_pending_files_slack_notification = self.make_slack_notification_task(
            'SendPendingFilesCheckedSlackNotification')
        send_checkfiles_finished_slack_notification = self.make_slack_notification_task(
            'SendCheckfilesFinishedSlackNotification')


        definition = check_pending_files.next(
            make_pending_files_checked_message
        ).next(
            send_pending_files_slack_notification
        ).next(
            Choice(self, 'Pending files?')
            .when(
                Condition.boolean_equals(
                    '$.files_pending', False), no_files_to_process
            ).otherwise(
                make_checkfiles_started_message.next(
                    send_checkfiles_started_notification
                ).next(                                     
                    initialize_counter
                ).next(
                    create_checkfiles_instance
                ).next(
                    wait_instance_ssm_registration
                ).next(
                    run_checkfiles_command
                ).next(
                    increment_counter
                ).next(
                    wait_for_five_minutes
                ).next(
                    get_checkfiles_command_status
                ).next(
                    make_progress_message
                ).next(
                    send_progress_notification
                ).next(
                    Choice(self, 'Should continue?')
                    .when(
                        Condition.and_(
                            Condition.boolean_equals(
                                '$.in_progress', True
                            ),
                            Condition.boolean_equals(
                                '$.iterator.continue', True
                            )
                        ), increment_counter
                    ).otherwise(
                        make_checkfiles_finished_message.next(
                            send_checkfiles_finished_slack_notification
                        ).next(
                            upload_report.next(
                                terminate_instance
                            )
                        )
                    )
                )
            )
        )

        state_machine = StateMachine(
            self,
            'StateMachine',
            definition=definition
        )

        state_machine_target = SfnStateMachine(
            state_machine
        )


    def make_slack_notification_task(self, task_id: str) -> EventBridgePutEvents:
        task = EventBridgePutEvents(
            self,
            task_id,
            entries=[
                EventBridgePutEventsEntry(
                    detail_type=JsonPath.string_at('$.detailType'),
                    detail=TaskInput.from_json_path_at('$.detail'),
                    source=JsonPath.string_at('$.source')
                )
            ],
            result_path=JsonPath.DISCARD,
        )
        return task
    
class RunCheckfilesStepFunctionProduction(RunCheckfilesStepFunction):
    pass
