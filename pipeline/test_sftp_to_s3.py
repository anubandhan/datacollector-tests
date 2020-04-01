# Copyright 2019 StreamSets Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import string

import pytest

from streamsets.sdk.utils import Version
from streamsets.testframework.markers import aws, sftp
from streamsets.testframework.utils import get_random_string

logger = logging.getLogger(__name__)

# Sandbox prefix for S3 bucket
S3_BUCKET_PREFIX = 'sftp_upload'


@aws('s3')
@pytest.mark.parametrize('read_ahead_stream', [True, False])
@sftp
def test_sftp_origin_whole_file_to_s3(sdc_builder, sdc_executor, sftp, aws, read_ahead_stream):
    """This is a test for SDC-11273.  First, it creates a large (~6MB) file and puts it on the SFTP server.
    Then, it creates a pipeline with SFTP origin and S3 destination, with whole file format, and runs
    until the single record (file) is complete.  Then, it asserts the S3 bucket contents are correct.
    We test for both scenarios: With Read Ahead Stream and without it.
    """
    sftp_file_name = get_random_string(string.ascii_letters, 10) + '.txt'
    raw_text_data = get_random_string(string.printable, 6000000)
    sftp.put_string(os.path.join(sftp.path, sftp_file_name), raw_text_data)

    s3_bucket = aws.s3_bucket_name
    s3_key = f'{S3_BUCKET_PREFIX}/{sftp_file_name}'

    # Build the pipeline
    builder = sdc_builder.get_pipeline_builder()

    sftp_ftp_client = builder.add_stage(name='com_streamsets_pipeline_stage_origin_remote_RemoteDownloadDSource')
    sftp_ftp_client.file_name_pattern = sftp_file_name
    sftp_ftp_client.data_format = 'WHOLE_FILE'
    if Version(sdc_builder.version) >= Version('3.8.2'):
        # Disable/Enable read-ahead stream.
        sftp_ftp_client.disable_read_ahead_stream = read_ahead_stream

    s3_destination = builder.add_stage('Amazon S3', type='destination')
    s3_destination.file_name_expression = "${record:value('/fileInfo/filename')}"
    s3_destination.set_attributes(bucket=s3_bucket, data_format='WHOLE_FILE', partition_prefix=s3_key)

    sftp_ftp_client >> s3_destination

    sftp_to_s3_pipeline = builder.build().configure_for_environment(aws, sftp)
    sdc_executor.add_pipeline(sftp_to_s3_pipeline)

    client = aws.s3
    try:
        # start pipeline and run for one record (the file)
        sdc_executor.start_pipeline(sftp_to_s3_pipeline).wait_for_pipeline_output_records_count(1)
        sdc_executor.stop_pipeline(sftp_to_s3_pipeline)

        # assert record count to S3 the size of the objects put
        list_s3_objs = client.list_objects_v2(Bucket=s3_bucket, Prefix=s3_key)
        assert len(list_s3_objs['Contents']) == 1

        # read data from S3 to assert contents
        s3_contents = [client.get_object(Bucket=s3_bucket, Key=s3_content['Key'])['Body'].read().decode()
                       for s3_content in list_s3_objs['Contents']]

        # compare the S3 bucket contents against the original whole file contents
        assert len(s3_contents[0]) == len(raw_text_data)
        assert s3_contents[0] == raw_text_data
    finally:
        delete_keys = {'Objects': [{'Key': k['Key']}
                                   for k in client.list_objects_v2(Bucket=s3_bucket, Prefix=s3_key)['Contents']]}
        client.delete_objects(Bucket=s3_bucket, Delete=delete_keys)
