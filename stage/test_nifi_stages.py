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

import pytest
from streamsets.testframework.markers import nifi, sdc_min_version

logger = logging.getLogger(__name__)

SNAPSHOT_TIMEOUT_SEC = 150

# This data is same as input in datacollector-tests/resources/nifi_templates/text_data_format_template.xml
EXPECTED_TEXT_DATA = ['Megan Rapinoe', 'Alex Morgan', 'Carli Lloyd']

DATA_FORMAT_TEMPLATES_MAP = {'TEXT': 'text_data_format_template.xml'}


@sdc_min_version('3.10.0')
@nifi
@pytest.mark.parametrize('data_format,expected_output',
                         [('TEXT', EXPECTED_TEXT_DATA)])
def test_basic_nifi_http_server(sdc_builder, sdc_executor, nifi, data_format, expected_output):
    """Integration test for the NiFi HTTP Server.

     1) Create NiFi pipeline which sends data (a Flowfile) to port 8000 of SDC container
     2) Create SDC pipeline that has a NiFi HTTP Server origin listening at port 8000 and trash as destination
     3) Start SDC pipeline with capture_snapshot.
     4) Start NiFi pipeline
     4) Finish snapshot in SDC pipeline and verify data received in snapshot is same as sent by NiFi pipeline.

     The pipeline looks like:
        nifi_http_server >> trash
    """

    # Build and start SDC pipeline.
    pipeline_builder = sdc_builder.get_pipeline_builder()
    nifi_http_server = pipeline_builder.add_stage('NiFi HTTP Server')
    nifi_http_server.data_format = data_format
    trash = pipeline_builder.add_stage('Trash')
    nifi_http_server >> trash
    pipeline = pipeline_builder.build().configure_for_environment(nifi)
    sdc_executor.add_pipeline(pipeline)

    try:
        # Start SDC pipeline along with snapshot capture.
        snapshot_pipeline_command = sdc_executor.capture_snapshot(pipeline, start_pipeline=True, wait=False)

        # Start NiFi pipeline.
        process_group, template = nifi.upload_template_and_start_process_group(DATA_FORMAT_TEMPLATES_MAP[data_format],
                                                                               sdc_executor.hostname,
                                                                               sdc_executor.docker_network)

        logger.debug('Finish the snapshot and verify')
        snapshot_command = snapshot_pipeline_command.wait_for_finished(timeout_sec=SNAPSHOT_TIMEOUT_SEC)
        snapshot = snapshot_command.snapshot

        # Stop SDC and NiFi pipelines.
        nifi.stop_process_group(process_group)
        sdc_executor.stop_pipeline(pipeline)

        output_records = snapshot[nifi_http_server.instance_name].output
        data_for_comparison = [record.field['text'].value for record in output_records]
        assert expected_output == data_for_comparison
    finally:
        if template:
            nifi.delete_template(template, DATA_FORMAT_TEMPLATES_MAP[data_format])
