# Copyright 2017 StreamSets Inc.
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

import json
import logging
import os
import pytest
import random
import string
import tempfile
import time
import csv
import textwrap

from streamsets.testframework.markers import sdc_min_version
from streamsets.testframework.utils import get_random_string

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

FILE_WRITER_SCRIPT = """
    file_contents = '''{file_contents}'''
    for record in records:
        with open('{filepath}', 'w') as f:
            f.write(file_contents.decode('utf8').encode('{encoding}'))
"""

FILE_WRITER_SCRIPT_BINARY = """
    with open('{filepath}', 'wb') as f:
        f.write({file_contents})
"""


@pytest.fixture(scope='module')
def sdc_common_hook():
    def hook(data_collector):
        data_collector.add_stage_lib('streamsets-datacollector-jython_2_7-lib')
    return hook


@pytest.fixture
def file_writer(sdc_executor):
    """Writes a file to SDC's local FS.

    Args:
        filepath (:obj:`str`): The absolute path to which to write the file.
        file_contents (:obj:`str`): The file contents.
        encoding (:obj:`str`, optional): The file encoding. Default: ``'utf8'``
        file_data_type (:obj:`str`, optional): The file which type of data containing . Default: ``'NOT_BINARY'``
    """
    def file_writer_(filepath, file_contents, encoding='utf8', file_data_type='NOT_BINARY'):
        write_file_with_pipeline(sdc_executor, filepath, file_contents, encoding, file_data_type)
    return file_writer_


def write_file_with_pipeline(sdc_executor, filepath, file_contents, encoding='utf8', file_data_type='NOT_BINARY'):
    builder = sdc_executor.get_pipeline_builder()
    dev_raw_data_source = builder.add_stage('Dev Raw Data Source')
    dev_raw_data_source.set_attributes(data_format='TEXT', raw_data='noop', stop_after_first_batch=True)
    jython_evaluator = builder.add_stage('Jython Evaluator')

    file_writer_script = FILE_WRITER_SCRIPT_BINARY if file_data_type == 'BINARY' else FILE_WRITER_SCRIPT
    jython_evaluator.script = textwrap.dedent(file_writer_script).format(filepath=str(filepath),
                                                                         file_contents=file_contents,
                                                                         encoding=encoding)
    trash = builder.add_stage('Trash')
    dev_raw_data_source >> jython_evaluator >> trash
    pipeline = builder.build('File writer pipeline')

    sdc_executor.add_pipeline(pipeline)
    sdc_executor.start_pipeline(pipeline).wait_for_finished()
    sdc_executor.remove_pipeline(pipeline)


@pytest.fixture
def shell_executor(sdc_executor):
    def shell_executor_(script, environment_variables=None):
        builder = sdc_executor.get_pipeline_builder()
        dev_raw_data_source = builder.add_stage('Dev Raw Data Source')
        dev_raw_data_source.set_attributes(data_format='TEXT', raw_data='noop', stop_after_first_batch=True)
        shell = builder.add_stage('Shell')
        shell.set_attributes(script=script,
                             environment_variables=(Configuration(**environment_variables)._data
                                                    if environment_variables
                                                    else []))
        trash = builder.add_stage('Trash')
        dev_raw_data_source >> [trash, shell]
        pipeline = builder.build('Shell executor pipeline')

        sdc_executor.add_pipeline(pipeline)
        sdc_executor.start_pipeline(pipeline).wait_for_finished()
        sdc_executor.remove_pipeline(pipeline)
    return shell_executor_


@pytest.fixture
def list_dir(sdc_executor):
    def list_dir_(data_format, files_directory, file_name_pattern, recursive=True, batches=1, batch_size=10):
        builder = sdc_executor.get_pipeline_builder()
        directory = builder.add_stage('Directory', type='origin')
        directory.set_attributes(data_format=data_format,
                                 file_name_pattern=file_name_pattern,
                                 file_name_pattern_mode='GLOB',
                                 files_directory=files_directory,
                                 process_subdirectories=recursive)

        trash = builder.add_stage('Trash')

        pipeline_finisher = builder.add_stage('Pipeline Finisher Executor')
        pipeline_finisher.set_attributes(preconditions=['${record:eventType() == \'no-more-data\'}'],
                                         on_record_error='DISCARD')

        directory >> trash
        directory >= pipeline_finisher

        pipeline = builder.build('List dir pipeline')
        sdc_executor.add_pipeline(pipeline)

        snapshot = sdc_executor.capture_snapshot(pipeline=pipeline,
                                                 batches=batches,
                                                 batch_size=batch_size,
                                                 start_pipeline=True).snapshot
        sdc_executor.stop_pipeline(pipeline)

        files = [str(record.field['filepath']) for b in range(len(snapshot.snapshot_batches))
                 for record in snapshot.snapshot_batches[b][directory.instance_name].event_records
                 if record.header.values['sdc.event.type'] == 'new-file']

        sdc_executor.remove_pipeline(pipeline)

        return files
    return list_dir_


# pylint: disable=pointless-statement, too-many-locals


def test_directory_origin(sdc_builder, sdc_executor):
    """Test Directory Origin. We test by making sure files are pre-created using Local FS destination stage pipeline
    and then have the Directory Origin read those files. The pipelines looks like:

        dev_raw_data_source >> local_fs
        directory >> trash

    """
    raw_data = 'Hello!'
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))

    # 1st pipeline which generates the required files for Directory Origin
    pipeline_builder = sdc_builder.get_pipeline_builder()
    dev_raw_data_source = pipeline_builder.add_stage('Dev Raw Data Source')
    dev_raw_data_source.set_attributes(data_format='TEXT', raw_data=raw_data)
    local_fs = pipeline_builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='TEXT',
                            directory_template=os.path.join(tmp_directory, '${YYYY()}-${MM()}-${DD()}-${hh()}'),
                            files_prefix='sdc-${sdc:id()}', files_suffix='txt', max_records_in_file=100)

    dev_raw_data_source >> local_fs
    files_pipeline = pipeline_builder.build('Generate files pipeline')
    sdc_executor.add_pipeline(files_pipeline)

    # generate some batches/files
    sdc_executor.start_pipeline(files_pipeline).wait_for_pipeline_batch_count(10)
    sdc_executor.stop_pipeline(files_pipeline)

    # 2nd pipeline which reads the files using Directory Origin stage
    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='TEXT', file_name_pattern='sdc*.txt', file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE', files_directory=tmp_directory,
                             process_subdirectories=True, read_order='TIMESTAMP')
    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build('Directory Origin pipeline')
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    # assert all the data captured have the same raw_data
    for record in snapshot.snapshot_batches[0][directory.instance_name].output:
        assert raw_data == record.field['text'].value
        assert record.header['sourceId'] is not None
        assert record.header['stageCreator'] is not None


@pytest.mark.parametrize('no_of_threads', [1, 5])
@sdc_min_version('3.1.0.0')
def test_directory_origin_order_by_timestamp(sdc_builder, sdc_executor, no_of_threads):
    """Test Directory Origin. We make sure we covered race condition
    when directory origin is configured order by last modified timestamp.
    The default wait time for directory spooler is 5 seconds,
    when the files are modified between 5 seconds make sure all files are processed.
    The pipelines looks like:

        dev_raw_data_source >> local_fs
        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))

    # 1st pipeline which writes one record per file with interval 0.1 seconds
    pipeline_builder = sdc_builder.get_pipeline_builder()
    dev_data_generator = pipeline_builder.add_stage('Dev Data Generator')
    dev_data_generator.set_attributes(batch_size=1,
                                      delay_between_batches=10)

    dev_data_generator.fields_to_generate = [{'field': 'text', 'precision': 10, 'scale': 2, 'type': 'STRING'}]

    local_fs = pipeline_builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='TEXT',
                            directory_template=os.path.join(tmp_directory),
                            files_prefix='sdc-${sdc:id()}', files_suffix='txt', max_records_in_file=1)

    dev_data_generator >> local_fs

    # run the 1st pipeline to create the directory and starting files
    files_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(files_pipeline)
    sdc_executor.start_pipeline(files_pipeline).wait_for_pipeline_batch_count(1)
    sdc_executor.stop_pipeline(files_pipeline)

    # 2nd pipeline which reads the files using Directory Origin stage
    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(batch_wait_time_in_secs=1,
                             data_format='TEXT', file_name_pattern='sdc*.txt',
                             file_name_pattern_mode='GLOB', file_post_processing='DELETE',
                             files_directory=tmp_directory, process_subdirectories=True,
                             read_order='TIMESTAMP', number_of_threads=no_of_threads)
    trash = pipeline_builder.add_stage('Trash')
    directory >> trash

    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)
    sdc_executor.start_pipeline(directory_pipeline)

    # re-run the 1st pipeline
    sdc_executor.start_pipeline(files_pipeline).wait_for_pipeline_batch_count(10)
    sdc_executor.stop_pipeline(files_pipeline)

    # wait till 2nd pipeline reads all files
    time.sleep(10)
    sdc_executor.stop_pipeline(directory_pipeline)

    # Validate history is as expected
    file_pipeline_history = sdc_executor.get_pipeline_history(files_pipeline)
    msgs_sent_count1 = file_pipeline_history.entries[4].metrics.counter('pipeline.batchOutputRecords.counter').count
    msgs_sent_count2 = file_pipeline_history.latest.metrics.counter('pipeline.batchOutputRecords.counter').count

    directory_pipeline_history = sdc_executor.get_pipeline_history(directory_pipeline)
    msgs_result_count = directory_pipeline_history.latest.metrics.counter('pipeline.batchOutputRecords.counter').count

    assert msgs_result_count == msgs_sent_count1 + msgs_sent_count2


@pytest.mark.parametrize('no_of_threads', [10])
@sdc_min_version('3.2.0.0')
def test_directory_origin_in_whole_file_dataformat(sdc_builder, sdc_executor, no_of_threads):
    """Test Directory Origin. We make sure multiple threads on whole data format works correct.
    The pipelines looks like:

        dev_raw_data_source >> local_fs
        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))

    # 1st pipeline which writes one record per file with interval 0.1 seconds
    pipeline_builder = sdc_builder.get_pipeline_builder()
    dev_data_generator = pipeline_builder.add_stage('Dev Data Generator')
    batch_size = 100
    dev_data_generator.set_attributes(batch_size=batch_size,
                                      delay_between_batches=10,
                                      number_of_threads=no_of_threads)

    dev_data_generator.fields_to_generate = [{'field': 'text', 'precision': 10, 'scale': 2, 'type': 'STRING'}]

    max_records_in_file = 10
    local_fs = pipeline_builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='TEXT',
                            directory_template=os.path.join(tmp_directory),
                            files_prefix='sdc-${sdc:id()}',
                            files_suffix='txt',
                            max_records_in_file=max_records_in_file)

    dev_data_generator >> local_fs

    number_of_batches = 5
    # run the 1st pipeline to create the directory and starting files
    files_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(files_pipeline)
    sdc_executor.start_pipeline(files_pipeline).wait_for_pipeline_batch_count(number_of_batches)
    sdc_executor.stop_pipeline(files_pipeline)

    # get the how many records are sent
    file_pipeline_history = sdc_executor.get_pipeline_history(files_pipeline)
    msgs_sent_count = file_pipeline_history.latest.metrics.counter('pipeline.batchOutputRecords.counter').count

    # compute the expected number of batches to process all files
    no_of_input_files = (msgs_sent_count / max_records_in_file)

    # 2nd pipeline which reads the files using Directory Origin stage in whole data format
    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(batch_wait_time_in_secs=1,
                             data_format='WHOLE_FILE',
                             max_files_in_directory=1000,
                             files_directory=tmp_directory,
                             file_name_pattern='*',
                             file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE',
                             number_of_threads=no_of_threads,
                             process_subdirectories=True,
                             read_order='TIMESTAMP')
    localfs = pipeline_builder.add_stage('Local FS', type='destination')
    localfs.set_attributes(data_format='WHOLE_FILE',
                           file_name_expression='${record:attribute(\'filename\')}')

    directory >> localfs

    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)
    sdc_executor.start_pipeline(directory_pipeline).wait_for_pipeline_batch_count(no_of_input_files)
    sdc_executor.stop_pipeline(directory_pipeline)

    directory_pipeline_history = sdc_executor.get_pipeline_history(directory_pipeline)
    msgs_result_count = directory_pipeline_history.latest.metrics.counter('pipeline.batchOutputRecords.counter').count

    assert msgs_result_count == no_of_input_files


@pytest.mark.parametrize('no_of_threads', [10])
@sdc_min_version('3.2.0.0')
def test_directory_origin_multiple_batches_no_initial_file(sdc_builder, sdc_executor, no_of_threads):
    """Test Directory Origin. We use the directory origin to read a batch of 100 files,
    after some times we will read a new batch of 100 files. No initial file configured.
    This test has been written to avoid regression, especially of issues raised in ESC-371
    The pipelines look like:

        Pipeline 1 (Local FS Target 1 in SDC UI): dev_data_generator >> local_fs_3 (in files_pipeline in the test)
        Pipeline 2 (Local FS Target 2 in SDC UI): dev_data_generator_2 >> local_fs_4 (in files_pipeline_2 in the test)
        Pipeline 3 (Directory Origin in SDC UI): directory >> local_fs
        Pipeline 4 (tmp_directory to tmp_directory_2 in SDC UI): directory_2 >> local_fs_2

        The test works as follows:
            1) Pipeline 1 writes files with prefix SDC1 to directory tmp_directory and then it is stopped
            2) Pipeline 3 is started and directory origin read files from directory tmp_directory. Pipeline is NOT
                stopped
            3) Pipeline 2 writes files with prefix SDC2 to directory tmp_directory_2 and then it is stopped
            4) Pipeline 4 reads files from directory tmp_directory_2 and writes them to directory tmp_directory, then
                it is stopped
            5) Pipeline 3 will read files Pipeline 4 writes to directory tmp_directory
            6) Test checks that all the corresponding files from directory tmp_directory are read and then test ends

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    tmp_directory_2 = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    number_of_batches = 5
    max_records_in_file = 10

    # run the 1st pipeline to create the directory and starting files
    files_pipeline = get_localfs_writer_pipeline(sdc_builder, no_of_threads, tmp_directory, max_records_in_file, 1)
    sdc_executor.add_pipeline(files_pipeline)
    sdc_executor.start_pipeline(files_pipeline).wait_for_pipeline_batch_count(number_of_batches)
    sdc_executor.stop_pipeline(files_pipeline)

    # get how many records are sent
    file_pipeline_history = sdc_executor.get_pipeline_history(files_pipeline)
    msgs_sent_count = file_pipeline_history.latest.metrics.counter('pipeline.batchOutputRecords.counter').count

    # compute the expected number of batches to process all files
    no_of_input_files = (msgs_sent_count / max_records_in_file)

    # 2nd pipeline which reads the files using Directory Origin stage in whole data format
    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(batch_wait_time_in_secs=1,
                             data_format='WHOLE_FILE',
                             max_files_in_directory=1000,
                             files_directory=tmp_directory,
                             file_name_pattern='*',
                             file_name_pattern_mode='GLOB',
                             number_of_threads=no_of_threads,
                             process_subdirectories=True,
                             read_order='LEXICOGRAPHICAL',
                             file_post_processing='DELETE')

    local_fs = pipeline_builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='WHOLE_FILE',
                            file_name_expression='${record:attribute(\'filename\')}')

    directory >> local_fs

    directory_pipeline = pipeline_builder.build(title='Directory Origin')
    sdc_executor.add_pipeline(directory_pipeline)
    pipeline_start_command = sdc_executor.start_pipeline(directory_pipeline)
    pipeline_start_command.wait_for_pipeline_batch_count(no_of_input_files)

    # Send another round of records while the reading pipeline is running
    files_pipeline_2 = get_localfs_writer_pipeline(sdc_builder, no_of_threads, tmp_directory_2, max_records_in_file, 2)
    sdc_executor.add_pipeline(files_pipeline_2)
    sdc_executor.start_pipeline(files_pipeline_2).wait_for_pipeline_batch_count(number_of_batches)
    sdc_executor.stop_pipeline(files_pipeline_2)

    file_pipeline_2_history = sdc_executor.get_pipeline_history(files_pipeline_2)
    msgs_sent_count_2 = file_pipeline_2_history.latest.metrics.counter('pipeline.batchOutputRecords.counter').count
    no_of_input_files_2 = (msgs_sent_count_2 / max_records_in_file)

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory_2 = pipeline_builder.add_stage('Directory', type='origin')
    directory_2.set_attributes(batch_wait_time_in_secs=1,
                             data_format='WHOLE_FILE',
                             max_files_in_directory=1000,
                             files_directory=tmp_directory_2,
                             file_name_pattern='*',
                             file_name_pattern_mode='GLOB',
                             number_of_threads=no_of_threads,
                             process_subdirectories=True,
                             read_order='LEXICOGRAPHICAL',
                             file_post_processing='DELETE')
    local_fs_2 = pipeline_builder.add_stage('Local FS', type='destination')
    local_fs_2.set_attributes(data_format='WHOLE_FILE',
                              file_name_expression='${record:attribute(\'filename\')}',
                              directory_template=tmp_directory,
                              files_prefix='')

    directory_2 >> local_fs_2

    directory_pipeline_2 = pipeline_builder.build(title='tmp_directory to tmp_directory_2')
    sdc_executor.add_pipeline(directory_pipeline_2)
    pipeline_start_command_2 = sdc_executor.start_pipeline(directory_pipeline_2)
    pipeline_start_command_2.wait_for_pipeline_batch_count(no_of_input_files_2)
    sdc_executor.stop_pipeline(directory_pipeline_2)

    # Wait until the pipeline reads all the expected files
    pipeline_start_command.wait_for_pipeline_batch_count(no_of_input_files + no_of_input_files_2)

    sdc_executor.stop_pipeline(directory_pipeline)
    directory_pipeline_history = sdc_executor.get_pipeline_history(directory_pipeline)
    msgs_result_count = directory_pipeline_history.latest.metrics.counter('pipeline.batchOutputRecords.counter').count

    assert msgs_result_count == (no_of_input_files + no_of_input_files_2)


def get_localfs_writer_pipeline(sdc_builder, no_of_threads, tmp_directory, max_records_in_file, index,
                                delay_between_batches=10):
    pipeline_builder = sdc_builder.get_pipeline_builder()
    dev_data_generator = pipeline_builder.add_stage('Dev Data Generator')
    batch_size = 100
    dev_data_generator.set_attributes(batch_size=batch_size,
                                      delay_between_batches=delay_between_batches,
                                      number_of_threads=no_of_threads)
    dev_data_generator.fields_to_generate = [{'field': 'text', 'precision': 10, 'scale': 2, 'type': 'STRING'}]

    local_fs = pipeline_builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='TEXT',
                            directory_template=os.path.join(tmp_directory),
                            files_prefix=f'sdc{index}-${{sdc:id()}}',
                            files_suffix='txt',
                            max_records_in_file=max_records_in_file)

    dev_data_generator >> local_fs

    files_pipeline = pipeline_builder.build(title=f'Local FS Target {index}')
    return files_pipeline


def test_directory_timestamp_ordering(sdc_builder, sdc_executor):
    """This test is mainly for SDC-10019.  The bug that was fixed there involves a race condition.  It only manifests if
    the files are ordered in increasing timestamp order and reverse alphabetical order AND the processing time required
    for a batch is sufficiently high.  That's why the pipeline is configured to write relatively large files (200k
    records, gzipped).

    Functionally, the test simply ensures that the second pipeline (with the directory origin) reads the same number of
    batches as was written by the first pipeline, and hence all data is read.  If the test times out, that essentially
    means that bug has occurred.
    """
    max_records_per_file = random.randint(100000, 300000)
    # randomize the batch size
    batch_size = random.randint(100, 5000)
    # generate enough batches to have 20 or so files
    num_batches = random.randint(15, 25) * max_records_per_file/batch_size

    random_str = get_random_string(string.ascii_letters, 10)
    tmp_directory = os.path.join(tempfile.gettempdir(), 'directory_timestamp_ordering', random_str, 'data')
    scratch_directory = os.path.join(tempfile.gettempdir(), 'directory_timestamp_ordering', random_str, 'scatch')
    logger.info('Test run information: num_batches=%d, batch_size=%d, max_records_per_file=%d, tmp_directory=%s, scratch_directory=%s',
                num_batches, batch_size, max_records_per_file, tmp_directory, scratch_directory)

    # use one pipeline to generate the .txt.gz files to be consumed by the directory pipeline
    pipeline_builder = sdc_builder.get_pipeline_builder()
    dev_data_generator = pipeline_builder.add_stage('Dev Data Generator')
    dev_data_generator.fields_to_generate = [{'field': 'text', 'precision': 10, 'scale': 2, 'type': 'STRING'}]
    dev_data_generator.set_attributes(delay_between_batches=0, batch_size=batch_size)
    local_fs = pipeline_builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='TEXT',
                            directory_template=tmp_directory,
                            files_prefix='sdc-${sdc:id()}',
                            files_suffix='txt',
                            compression_codec='GZIP',
                            max_records_in_file=max_records_per_file)

    dev_data_generator >> local_fs
    shell_executor = pipeline_builder.add_stage('Shell')
    shell_executor.set_attributes(stage_record_preconditions=["${record:eventType() == 'file-closed'}"])
    shell_executor.set_attributes(environment_variables=[{'key': 'FILENAME', 'value': '${record:value(\'/filename\')}'},
                                                         {'key': 'FILEPATH', 'value': '${record:value(\'/filepath\')}'}])
    # this script will rename the completed txt.gz file to be of the form WORD_TIMESTAMP.txt.gz where WORD is chosen from
    # a reverse-alphabetical list of cycling words and TIMESTAMP is the current timestamp, and also ; this ensures that newer files
    # (i.e. those written later in the pipeline execution) will sometimes have earlier lexicographical orderings to
    # trigger SDC-10091

    shell_executor.set_attributes(script=f'''\
#!/bin/bash

if [[ ! -s {scratch_directory}/count.txt ]]; then
  echo '0' > {scratch_directory}/count.txt
fi
COUNT=$(cat {scratch_directory}/count.txt)
echo $(($COUNT+1)) > {scratch_directory}/count.txt

if [[ ! -s {scratch_directory}/words.txt ]]; then
  mkdir -p {scratch_directory}
  echo 'eggplant
dill
cucumber
broccoli
apple' > {scratch_directory}/words.txt
  WORD=fig
else
  WORD=$(head -1 {scratch_directory}/words.txt)
  grep -v $WORD {scratch_directory}/words.txt > {scratch_directory}/words_new.txt
  mv {scratch_directory}/words_new.txt {scratch_directory}/words.txt
fi

RAND_NUM=$(($RANDOM % 10))
SUBDIR="subdir${{RAND_NUM}}"
cd $(dirname $FILEPATH)
mkdir -p $SUBDIR
mv $FILENAME $SUBDIR/${{WORD}}_$COUNT.txt.gz
    ''')
    local_fs >= shell_executor
    files_pipeline = pipeline_builder.build('Generate files pipeline')
    sdc_executor.add_pipeline(files_pipeline)

    # generate the input files
    sdc_executor.start_pipeline(files_pipeline).wait_for_pipeline_batch_count(num_batches)
    sdc_executor.stop_pipeline(files_pipeline)

    # create the actual directory origin pipeline, which will read the generated *.txt.gz files (across
    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='TEXT',
                             file_name_pattern='*.txt.gz',
                             file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE',
                             files_directory=tmp_directory,
                             process_subdirectories=True,
                             read_order='TIMESTAMP',
                             compression_format='COMPRESSED_FILE',
                             batch_size_in_recs=batch_size)
    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build('Directory Origin pipeline')
    sdc_executor.add_pipeline(directory_pipeline)

    # if we set the batch size to the same value in the directory origin pipeline, it should read exactly as many batches
    # as were written by the first pipeline
    sdc_executor.start_pipeline(directory_pipeline).wait_for_pipeline_batch_count(num_batches)
    sdc_executor.stop_pipeline(directory_pipeline)


@sdc_min_version('3.0.0.0')
def test_directory_origin_avro_produce_less_file(sdc_builder, sdc_executor):
    """Test Directory Origin in Avro data format. The sample Avro file has 5 lines and
    the batch size is 1. The pipeline should produce the event, "new-file" and 1 record

    The pipelines looks like:

        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    avro_records = setup_avro_file(sdc_executor, tmp_directory)

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='AVRO', file_name_pattern='sdc*', file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE', files_directory=tmp_directory,
                             process_subdirectories=True, read_order='TIMESTAMP')
    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=1).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    # assert all the data captured have the same raw_data
    output_records = snapshot[directory.instance_name].output
    event_records = snapshot[directory.instance_name].event_records

    assert 1 == len(event_records)
    assert 1 == len(output_records)

    assert 'new-file' == event_records[0].header['values']['sdc.event.type']

    assert output_records[0].get_field_data('/name') == avro_records[0].get('name')
    assert output_records[0].get_field_data('/age') == avro_records[0].get('age')
    assert output_records[0].get_field_data('/emails') == avro_records[0].get('emails')
    assert output_records[0].get_field_data('/boss') == avro_records[0].get('boss')


@sdc_min_version('3.8.0')
def test_directory_origin_multiple_threads_no_more_data_sent_after_all_data_read(sdc_builder, sdc_executor):
    """Test that directory origin with more than one threads read all data from all the files in a folder before
    sending no more data event.

    The pipelines looks like:

        directory >> trash
        directory >= pipeline finisher executor
    """

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='DELIMITED', header_line='WITH_HEADER', file_name_pattern='test*.csv',
                             file_name_pattern_mode='GLOB', file_post_processing='NONE',
                             files_directory='/resources/resources/directory_origin', read_order='LEXICOGRAPHICAL',
                             batch_size_in_recs=10, batch_wait_time_in_secs=60,
                             number_of_threads=3, on_record_error='STOP_PIPELINE')
    trash = pipeline_builder.add_stage('Trash')

    directory >> trash

    pipeline_finisher_executor = pipeline_builder.add_stage('Pipeline Finisher Executor')
    pipeline_finisher_executor.set_attributes(preconditions=['${record:eventType() == \'no-more-data\'}'],
                                              on_record_error='DISCARD')

    directory >= pipeline_finisher_executor

    directory_pipeline = pipeline_builder.build(
        title='test_directory_origin_multiple_threads_no_more_data_sent_after_all_data_read')
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=10,
                                             batches=14, wait_for_statuses=['FINISHED'], timeout_sec=120).snapshot

    # assert all the data captured have the same raw_data
    output_records = [record for i in range(len(snapshot.snapshot_batches)) for record in
                      snapshot.snapshot_batches[i][directory.instance_name].output]

    output_records_text_fields = [f'{record.field["Name"]},{record.field["Job"]},{record.field["Salary"]}' for record in
                                  output_records]

    temp_data_from_csv_file = (read_csv_file('./resources/directory_origin/test4.csv', ',', True))
    data_from_csv_files = [f'{row[0]},{row[1]},{row[2]}' for row in temp_data_from_csv_file]
    temp_data_from_csv_file = (read_csv_file('./resources/directory_origin/test5.csv', ',', True))
    for row in temp_data_from_csv_file:
        data_from_csv_files.append(f'{row[0]},{row[1]},{row[2]}')
    temp_data_from_csv_file = (read_csv_file('./resources/directory_origin/test6.csv', ',', True))
    for row in temp_data_from_csv_file:
        data_from_csv_files.append(f'{row[0]},{row[1]},{row[2]}')

    assert len(data_from_csv_files) == len(output_records_text_fields)
    assert sorted(data_from_csv_files) == sorted(output_records_text_fields)


@sdc_min_version('3.0.0.0')
def test_directory_origin_avro_produce_full_file(sdc_builder, sdc_executor):
    """ Test Directory Origin in Avro data format. The sample Avro file has 5 lines and
    the batch size is 10. The pipeline should produce the event, "new-file" and "finished-file"
    and 5 records

    The pipelines looks like:

        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    avro_records = setup_avro_file(sdc_executor, tmp_directory)

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='AVRO', file_name_pattern='sdc*', file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE', files_directory=tmp_directory,
                             process_subdirectories=True, read_order='TIMESTAMP')
    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=10).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    # assert all the data captured have the same raw_data
    output_records = snapshot[directory.instance_name].output
    event_records = snapshot[directory.instance_name].event_records

    assert 2 == len(event_records)
    assert 5 == len(output_records)

    assert 'new-file' == event_records[0].header['values']['sdc.event.type']
    assert 'finished-file' == event_records[1].header['values']['sdc.event.type']

    for i in range(0, 5):
        assert output_records[i].get_field_data('/name') == avro_records[i].get('name')
        assert output_records[i].get_field_data('/age') == avro_records[i].get('age')
        assert output_records[i].get_field_data('/emails') == avro_records[i].get('emails')
        assert output_records[i].get_field_data('/boss') == avro_records[i].get('boss')


@sdc_min_version('3.12.0')
@pytest.mark.parametrize('csv_record_type', ['LIST_MAP','LIST'])
def test_directory_origin_bom_file(sdc_builder, sdc_executor, csv_record_type):
    """ Test Directory Origin with file in CSV data format and containing BOM.
    The file(file_with_bom.csv) is present in resources/directory_origin. To view the
    BOM bytes, we can use "hexdump -C file_with_bom.csv". The first 3 bytes(ef bb bf)
    are BOM.

    The pipeline looks like:

        directory >> trash

    """
    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')

    directory.set_attributes(data_format='DELIMITED',
                             file_name_pattern='file_with_bom.csv',
                             file_name_pattern_mode='GLOB',
                             files_directory='/resources/resources/directory_origin',
                             process_subdirectories=True,
                             read_order='TIMESTAMP',
                             root_field_type=csv_record_type)

    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=10).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    output_records = snapshot[directory.instance_name].output

    # contents of file_with_bom.csv: <BOM>abc,123,xyz
    if csv_record_type == 'LIST_MAP':
        assert 'abc' == output_records[0].get_field_data('/0')
        assert '123' == output_records[0].get_field_data('/1')
        assert 'xyz' == output_records[0].get_field_data('/2')
    else:
        assert 'abc' == output_records[0].get_field_data('/0').get('value')
        assert '123' == output_records[0].get_field_data('/1').get('value')
        assert 'xyz' == output_records[0].get_field_data('/2').get('value')


@sdc_min_version('3.0.0.0')
@pytest.mark.parametrize('csv_record_type', ['LIST_MAP', 'LIST'])
def test_directory_origin_csv_produce_full_file(sdc_builder, sdc_executor, csv_record_type):
    """ Test Directory Origin in CSV data format. The sample CSV file has 3 lines and
    the batch size is 10. The pipeline should produce the event, "new-file" and "finished-file"
    and 3 records

    The pipelines looks like:

        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    csv_records = setup_basic_dilimited_file(sdc_executor, tmp_directory)

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')

    directory.set_attributes(data_format='DELIMITED',
                             file_name_pattern='sdc*', file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE', files_directory=tmp_directory,
                             process_subdirectories=True, read_order='TIMESTAMP',
                             root_field_type=csv_record_type)

    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=10).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    # assert all the data captured have the same csv_records
    output_records = snapshot[directory.instance_name].output
    event_records = snapshot[directory.instance_name].event_records

    assert 2 == len(event_records)
    assert 3 == len(output_records)

    assert 'new-file' == event_records[0].header['values']['sdc.event.type']
    assert 'finished-file' == event_records[1].header['values']['sdc.event.type']

    for i in range(0, 3):
        csv_record_fields = csv_records[i].split(',')
        for j in range(0, len(csv_record_fields)):
            if type(output_records[i].get_field_data(f'/{j}')) is dict:
               output_records[i].get_field_data(f'/{j}').get('value') == csv_record_fields[j]
            else:
                output_records[i].get_field_data(f'/{j}') == csv_record_fields[j]


@sdc_min_version('3.0.0.0')
@pytest.mark.parametrize('csv_record_type', ['LIST_MAP', 'LIST'])
@pytest.mark.parametrize('header_line', ['WITH_HEADER', 'IGNORE_HEADER', 'NO_HEADER'])
def test_directory_origin_csv_produce_less_file(sdc_builder, sdc_executor, csv_record_type, header_line):
    """ Test Directory Origin in CSV data format. The sample CSV file has 3 lines and
    the batch size is 1. The pipeline should produce the event, "new-file"
    and 1 record

    The pipelines looks like:

        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    csv_records = setup_basic_dilimited_file(sdc_executor, tmp_directory)

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='DELIMITED',
                             file_name_pattern='sdc*', file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE', files_directory=tmp_directory,
                             header_line=header_line, process_subdirectories=True,
                             read_order='TIMESTAMP', root_field_type=csv_record_type)
    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=1).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    # assert all the data captured have the same csv_records
    output_records = snapshot[directory.instance_name].output
    event_records = snapshot[directory.instance_name].event_records

    assert 1 == len(event_records)
    assert 1 == len(output_records)

    assert 'new-file' == event_records[0].header['values']['sdc.event.type']

    csv_record_fields = csv_records[0].split(',')
    for j in range(0, len(csv_record_fields)):
        name = csv_record_fields[j] if header_line == 'WITH_HEADER' and csv_record_type == 'LIST_MAP' else j
        if type(output_records[0].get_field_data(f'/{name}')) is dict:
           output_records[0].get_field_data(f'/{name}').get('value') == csv_record_fields[j]
        else:
            output_records[0].get_field_data(f'/{name}') == csv_record_fields[j]


@sdc_min_version('3.0.0.0')
def test_directory_origin_csv_custom_file(sdc_builder, sdc_executor):
    """ Test Directory Origin in custom CSV data format. The sample CSV file has 1 custom CSV

    The pipelines looks like:

        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    csv_records = setup_custom_delimited_file(sdc_executor, tmp_directory)

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='DELIMITED', delimiter_format_type='CUSTOM',
                             file_name_pattern='sdc*', file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE', files_directory=tmp_directory,
                             process_subdirectories=True, read_order='TIMESTAMP')
    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=1).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    output_records = snapshot[directory.instance_name].output

    assert 1 == len(output_records)
    assert output_records[0].get_field_data('/0') == ' '.join(csv_records)

@sdc_min_version('3.8.0')
def test_directory_origin_multi_char_delimited(sdc_builder, sdc_executor):
    """
    Test Directory Origin with multi-character delimited format. This will generate a sample file with the custom
    multi-char delimiter then read it with the test pipeline.

    The pipeline looks like:

        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    # crazy delimiter
    delim = '_/-\\_'
    custom_delimited_lines = [
      f"first{delim}second{delim}third",
      f"1{delim}11{delim}111",
      f"2{delim}22{delim}222",
      f"31{delim}3,3{delim}3,_/-_3,3"
    ]
    setup_dilimited_file(sdc_executor, tmp_directory, custom_delimited_lines)

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='DELIMITED', delimiter_format_type='MULTI_CHARACTER',
                             multi_character_field_delimiter=delim,
                             header_line='WITH_HEADER',
                             file_name_pattern='sdc*', file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE', files_directory=tmp_directory,
                             process_subdirectories=True, read_order='TIMESTAMP')
    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build('Multi Char Delimited Directory')
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=3).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    output_records = snapshot[directory.instance_name].output

    assert 3 == len(output_records)
    assert output_records[0].get_field_data('/first') == '1'
    assert output_records[0].get_field_data('/second') == '11'
    assert output_records[0].get_field_data('/third') == '111'
    assert output_records[1].get_field_data('/first') == '2'
    assert output_records[1].get_field_data('/second') == '22'
    assert output_records[1].get_field_data('/third') == '222'
    assert output_records[2].get_field_data('/first') == '31'
    assert output_records[2].get_field_data('/second') == '3,3'
    assert output_records[2].get_field_data('/third') == '3,_/-_3,3'

@sdc_min_version('3.0.0.0')
def test_directory_origin_csv_custom_comment_file(sdc_builder, sdc_executor):
    """ Test Directory Origin in custom CSV data format with comment enabled. The sample CSV file have
    1 delimited line follow by 1 comment line and 1 delimited line

    The pipelines looks like:

        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    csv_records = setup_dilimited_with_comment_file(sdc_executor, tmp_directory)

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='DELIMITED', delimiter_format_type='CUSTOM',
                             file_name_pattern='sdc*', file_name_pattern_mode='GLOB',
                             enable_comments = True,
                             file_post_processing='DELETE',
                             files_directory=tmp_directory,
                             process_subdirectories=True, read_order='TIMESTAMP')
    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=10).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    # assert all the data captured have the same raw_data
    output_records = snapshot[directory.instance_name].output

    assert 2 == len(output_records)

    assert output_records[0].get_field_data('/0') == csv_records[0]
    assert output_records[1].get_field_data('/0') == csv_records[2]


@sdc_min_version('3.0.0.0')
@pytest.mark.parametrize('ignore_empty_line', [True, False])
def test_directory_origin_custom_csv_empty_line_file(sdc_builder, sdc_executor, ignore_empty_line):
    """ Test Directory Origin in custom CSV data format with empty line enabled and disabled.
    The sample CSV file has 2 CSV records and 1 empty line.
    The pipeline should produce 2 when empty line is enabled and 3 when empty line is disabled

    The pipelines looks like:

        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    csv_records = setup_dilimited_with_empty_line_file(sdc_executor, tmp_directory)
    empty_line_position = [1]

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='DELIMITED', delimiter_format_type='CUSTOM',
                             ignore_empty_lines = ignore_empty_line,
                             file_name_pattern='sdc*', file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE',
                             files_directory=tmp_directory,
                             process_subdirectories=True, read_order='TIMESTAMP')
    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=10).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    # assert all the data captured have the same raw_data
    output_records = snapshot[directory.instance_name].output

    expected_record_size = len(csv_records)
    if ignore_empty_line:
        expected_record_size = 2
    assert expected_record_size == len(output_records)

    assert output_records[0].get_field_data('/0') == csv_records[0]

    if ignore_empty_line:
        assert output_records[1].get_field_data('/0') == csv_records[2]
    else:
        assert output_records[2].get_field_data('/0') == csv_records[2]


@sdc_min_version('3.0.0.0')
@pytest.mark.parametrize('batch_size', [3,4,5,6])
def test_directory_origin_csv_record_overrun_on_batch_boundary(sdc_builder, sdc_executor, batch_size):
    """ Test Directory Origin in Delimited data format. The long delimited record in [2,4,5,8,9]th in the file
    the long delimited record should be ignored in the batch

    The pipelines looks like:

        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    csv_records = setup_long_dilimited_file(sdc_executor, tmp_directory)
    long_dilimited_record_position = [2,4,5,8,9]

    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='DELIMITED',
                             file_name_pattern='sdc*', file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE', files_directory=tmp_directory,
                             max_record_length_in_chars=10,
                             process_subdirectories=True, read_order='TIMESTAMP')


    trash = pipeline_builder.add_stage('Trash')

    directory >> trash
    directory_pipeline = pipeline_builder.build()
    sdc_executor.add_pipeline(directory_pipeline)

    snapshot = sdc_executor.capture_snapshot(directory_pipeline, start_pipeline=True, batch_size=batch_size).snapshot
    sdc_executor.stop_pipeline(directory_pipeline)

    # assert all the data captured have the same raw_data
    output_records = snapshot[directory.instance_name].output

    expected_batch_size = batch_size
    for i in range(0, batch_size):
        if i in long_dilimited_record_position:
            expected_batch_size = expected_batch_size - 1

    assert expected_batch_size == len(output_records)

    j = 0
    for i in range(0, batch_size):
        if j not in long_dilimited_record_position:
            csv_record_fields = csv_records[j].split(',')
            for k in range(0, len(csv_record_fields)):
                output_records[0].get_field_data(f'/{k}') == csv_record_fields[k]
            j = j + 1


# SDC-10424
@sdc_min_version('3.5.3')
def test_directory_post_delete_on_batch_failure(sdc_builder, sdc_executor):
    """Make sure that post-actions are not executed on batch failure."""
    raw_data = '1\n2\n3\n4\n5'
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))

    # 1st pipeline which generates the required files for Directory Origin
    builder = sdc_builder.get_pipeline_builder()
    origin = builder.add_stage('Dev Raw Data Source')
    origin.stop_after_first_batch = True
    origin.set_attributes(data_format='TEXT', raw_data=raw_data)

    local_fs = builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='TEXT',
                            directory_template=os.path.join(tmp_directory, '${YYYY()}-${MM()}-${DD()}-${hh()}'),
                            files_prefix='sdc-${sdc:id()}',
                            files_suffix='txt',
                            max_records_in_file=100)

    origin >> local_fs
    files_pipeline = builder.build('Generate files pipeline')
    sdc_executor.add_pipeline(files_pipeline)

    # Generate exactly one input file
    sdc_executor.start_pipeline(files_pipeline).wait_for_finished()

    # 2nd pipeline which reads the files using Directory Origin stage
    builder = sdc_builder.get_pipeline_builder()
    directory = builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='TEXT',
                             file_name_pattern='sdc*.txt',
                             file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE',
                             files_directory=tmp_directory,
                             process_subdirectories=True,
                             read_order='TIMESTAMP')
    shell = builder.add_stage('Shell')
    shell.script = "return -1"
    shell.on_record_error = "STOP_PIPELINE"

    directory >> shell
    directory_pipeline = builder.build('Directory Origin pipeline')
    sdc_executor.add_pipeline(directory_pipeline)

    sdc_executor.start_pipeline(directory_pipeline, wait=False).wait_for_status(status='RUN_ERROR', ignore_errors=True)

    # The main check is now - the pipeline should not drop the input file
    builder = sdc_builder.get_pipeline_builder()
    origin = builder.add_stage('Directory')
    origin.set_attributes(data_format='WHOLE_FILE',
                          file_name_pattern='sdc*.txt',
                          file_name_pattern_mode='GLOB',
                          file_post_processing='DELETE',
                          files_directory=tmp_directory,
                          process_subdirectories=True,
                          read_order='TIMESTAMP')
    trash = builder.add_stage('Trash')
    origin >> trash

    pipeline = builder.build('Validation')
    sdc_executor.add_pipeline(pipeline)

    snapshot = sdc_executor.capture_snapshot(pipeline, start_pipeline=True).snapshot
    sdc_executor.stop_pipeline(pipeline)
    assert 1 == len(snapshot[origin.instance_name].output)

# SDC-13559: Directory origin fires one batch after another when Allow Late directories is in effect
def test_directory_allow_late_directory_wait_time(sdc_builder, sdc_executor):
    """Test to ensure that when user explicitly enables "Allow Late Directory" and the directory doesn't exists,
    the origin won't go into a mode where it will generate one batch after another, ignoring the option Batch Wait
    Time completely."""
    builder = sdc_builder.get_pipeline_builder()
    directory = builder.add_stage('Directory', type='origin')
    directory.data_format = 'TEXT'
    directory.file_name_pattern = 'sdc*.txt'
    directory.files_directory = '/i/do/not/exists'
    directory.allow_late_directory = True
    trash = builder.add_stage('Trash')

    directory >> trash
    pipeline = builder.build()
    sdc_executor.add_pipeline(pipeline)

    sdc_executor.start_pipeline(pipeline)
    # We let the pipeline run for ~10 seconds - enough time to validate whether the origin is creating one batch
    # after another or not.
    time.sleep(10)
    sdc_executor.stop_pipeline(pipeline)

    # The origin and/or pipeline can still generate some batches, so we don't test precise number, just that is
    # really small (less then 1 batch/second).
    history = sdc_executor.get_pipeline_history(pipeline)
    assert history.latest.metrics.counter('pipeline.batchCount.counter').count < 5


# Test for SDC-13476
def test_directory_origin_read_different_file_type(sdc_builder, sdc_executor):
    """Test Directory Origin. We make sure we covered race condition
    when directory origin is configured with JSON data format but files directory have txt files.
    It shows the relative stage errors depending on the type of file we try to read from files directory.
    The pipelines looks like:

        dev_raw_data_source >> local_fs
        directory >> trash

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    generate_files(sdc_builder, sdc_executor, tmp_directory)

    # 2nd pipeline which reads the files using Directory Origin stage
    builder = sdc_builder.get_pipeline_builder()
    directory = builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='JSON',
                             file_name_pattern='*',
                             number_of_threads=10,
                             file_name_pattern_mode='GLOB',
                             file_post_processing='DELETE',
                             files_directory=tmp_directory,
                             error_directory=tmp_directory,
                             read_order='LEXICOGRAPHICAL')
    trash = builder.add_stage('Trash')
    directory >> trash

    pipeline = builder.build('Validation')
    sdc_executor.add_pipeline(pipeline)

    snapshot = sdc_executor.capture_snapshot(pipeline, start_pipeline=True).snapshot

    assert 10 == len(sdc_executor.get_stage_errors(pipeline, directory))

    sdc_executor.stop_pipeline(pipeline)

    output_records = snapshot[directory.instance_name].output

    assert 0 == len(output_records)


@pytest.mark.parametrize('no_of_threads', [4])
@sdc_min_version('3.2.0.0')
def test_directory_origin_multiple_threads_timestamp_ordering(sdc_builder, sdc_executor, no_of_threads):
    """Test Directory Origin. We test that we read the same amount of files that we write with no reprocessing
    of files and no NoSuchFileException in the sdc logs

    Pipeline looks like:

    Dev Data Generator >> Local FS (files_pipeline in the test)
    Directory Origin >> Trash

    """

    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    number_of_batches = 100
    max_records_in_file = 10

    # Start files_pipeline
    files_pipeline = get_localfs_writer_pipeline(sdc_builder, no_of_threads, tmp_directory, max_records_in_file, 1,
                                                 2000)
    sdc_executor.add_pipeline(files_pipeline)
    start_pipeline_command = sdc_executor.start_pipeline(files_pipeline)

    # 2nd pipeline which reads the files using Directory Origin stage in whole data format
    pipeline_builder = sdc_builder.get_pipeline_builder()
    directory = pipeline_builder.add_stage('Directory', type='origin')
    directory.set_attributes(batch_wait_time_in_secs=1,
                             data_format='WHOLE_FILE',
                             max_files_in_directory=1000,
                             files_directory=tmp_directory,
                             file_name_pattern='*',
                             file_name_pattern_mode='GLOB',
                             number_of_threads=no_of_threads,
                             process_subdirectories=True,
                             read_order='TIMESTAMP',
                             file_post_processing='DELETE')

    trash = pipeline_builder.add_stage('Trash')

    directory >> trash

    directory_pipeline = pipeline_builder.build(title='Directory Origin')
    sdc_executor.add_pipeline(directory_pipeline)
    pipeline_start_command = sdc_executor.start_pipeline(directory_pipeline)

    # Stop files_pipeline after number_of_batches or more
    start_pipeline_command.wait_for_pipeline_batch_count(number_of_batches)
    sdc_executor.stop_pipeline(files_pipeline)

    # Get how many records are sent
    file_pipeline_history = sdc_executor.get_pipeline_history(files_pipeline)
    msgs_sent_count = file_pipeline_history.latest.metrics.counter('pipeline.batchOutputRecords.counter').count

    # Compute the expected number of batches to process all files
    no_of_input_files = (msgs_sent_count / max_records_in_file)

    pipeline_start_command.wait_for_pipeline_batch_count(no_of_input_files)

    assert 0 == len(sdc_executor.get_stage_errors(directory_pipeline, directory))

    sdc_executor.stop_pipeline(directory_pipeline)
    directory_pipeline_history = sdc_executor.get_pipeline_history(directory_pipeline)
    msgs_result_count = directory_pipeline_history.latest.metrics.counter('pipeline.batchOutputRecords.counter').count

    assert msgs_result_count == no_of_input_files


# Test for SDC-13486
def test_directory_origin_error_file_to_error_dir(sdc_builder, sdc_executor):
    """ Test Directory Origin. Create two files in tmp_directory file1.txt which is correctly parsed by directory
    origin and file2.txt which is not correctly parsed by directory origin and hence it is sent to tmp_error_directory
    by that directory origin. After that we check with another directory origin reading from tmp_error_directory that
    we get an error_record specifying that file2.txt cannot be parsed again so we have checked that file2.txt was moved
    to tmp_error_directory by the first directory origin.

    Pipelines look like:

        dev_raw_data_source >> local_fs (called Custom Generate file1.txt pipeline)
        dev_raw_data_source >> local_fs (called Custom Generate file2.txt pipeline)
        dev_raw_data_source >= shell (events lane for the same pipeline as in above comment)
        directory >> trash (called Directory Read file1.txt and file2.txt)
        directory >> trash (called Directory Read file2.txt from error directory)

    """
    tmp_directory = os.path.join(tempfile.gettempdir(), get_random_string(string.ascii_letters, 10))
    tmp_error_directory = os.path.join(tempfile.mkdtemp(prefix="err_dir_", dir=tempfile.gettempdir()))

    headers = "publication_title	print_identifier	online_identifier\n"

    # Generate file1.txt with good data.
    raw_data = headers + "abcd  efgh    ijkl\n"
    pipeline_builder = sdc_executor.get_pipeline_builder()
    dev_raw_data_source = pipeline_builder.add_stage('Dev Raw Data Source')
    dev_raw_data_source.set_attributes(data_format='TEXT',
                                       raw_data=raw_data,
                                       stop_after_first_batch=True,
                                       event_data='create-directory')
    local_fs = pipeline_builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='TEXT',
                            directory_template=tmp_directory,
                            files_prefix='file1', files_suffix='txt')

    dev_raw_data_source >> local_fs

    files_pipeline = pipeline_builder.build('Custom Generate file1.txt pipeline')
    sdc_executor.add_pipeline(files_pipeline)

    logger.debug("Creating file1.txt")
    sdc_executor.start_pipeline(files_pipeline).wait_for_finished(timeout_sec=5)

    # Generate file2.txt with bad data and create error directory.
    raw_data = headers + f'''ab	"	"'	''abcd		efgh\n'''
    dev_raw_data_source.set_attributes(raw_data=raw_data)
    local_fs.set_attributes(files_prefix='file2')

    shell = pipeline_builder.add_stage('Shell')
    shell.set_attributes(preconditions=["${record:value('/text') == 'create-directory'}"],
                         script=f'''mkdir {tmp_error_directory}''')

    dev_raw_data_source >= shell

    files_pipeline_2 = pipeline_builder.build('Custom Generate file2.txt pipeline')
    sdc_executor.add_pipeline(files_pipeline_2)

    logger.debug("Creating file2.txt")
    sdc_executor.start_pipeline(files_pipeline_2).wait_for_finished(timeout_sec=5)

    # 1st Directory pipeline which tries to read both file1.txt and file2.txt.
    builder = sdc_builder.get_pipeline_builder()
    directory = builder.add_stage('Directory', type='origin')
    directory.set_attributes(file_name_pattern='*.txt',
                             number_of_threads=2,
                             file_name_pattern_mode='GLOB',
                             file_post_processing='NONE',
                             files_directory=tmp_directory,
                             error_directory=tmp_error_directory,
                             read_order='LEXICOGRAPHICAL',
                             data_format='DELIMITED',
                             header_line='WITH_HEADER',
                             delimiter_format_type='TDF')  # Tab separated values.
    trash = builder.add_stage('Trash')
    directory >> trash

    pipeline_dir = builder.build('Directory Read file1.txt and file2.txt')
    sdc_executor.add_pipeline(pipeline_dir)

    sdc_executor.start_pipeline(pipeline_dir)

    assert 1 == len(sdc_executor.get_stage_errors(pipeline_dir, directory))
    assert "file2" in sdc_executor.get_stage_errors(pipeline_dir, directory)[0].error_message

    sdc_executor.stop_pipeline(pipeline_dir)

    # 2nd Directory pipeline which will read from error directory to check file2.txt is there.
    builder = sdc_builder.get_pipeline_builder()
    directory_error = builder.add_stage('Directory', type='origin')
    directory_error.set_attributes(file_name_pattern='*.txt',
                                   number_of_threads=2,
                                   file_name_pattern_mode='GLOB',
                                   file_post_processing='NONE',
                                   files_directory=tmp_error_directory,
                                   error_directory=tmp_error_directory,
                                   read_order='LEXICOGRAPHICAL',
                                   data_format='DELIMITED',
                                   header_line='WITH_HEADER',
                                   delimiter_format_type='TDF')  # Tab separated values.
    trash_2 = builder.add_stage('Trash')
    directory_error >> trash_2

    pipeline_error_dir = builder.build('Directory Read file2.txt from error directory')
    sdc_executor.add_pipeline(pipeline_error_dir)

    sdc_executor.start_pipeline(pipeline_error_dir)

    assert 1 == len(sdc_executor.get_stage_errors(pipeline_error_dir, directory))
    assert "file2" in sdc_executor.get_stage_errors(pipeline_error_dir, directory)[0].error_message

    sdc_executor.stop_pipeline(pipeline_error_dir)


def generate_files(sdc_builder, sdc_executor, tmp_directory):
    raw_data = 'Hello!'

    # pipeline which generates the required files for Directory Origin
    builder = sdc_builder.get_pipeline_builder()
    dev_raw_data_source = builder.add_stage('Dev Raw Data Source')
    dev_raw_data_source.set_attributes(data_format='TEXT', raw_data=raw_data)
    local_fs = builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='TEXT',
                            directory_template=tmp_directory,
                            files_prefix='sdc-${sdc:id()}',
                            files_suffix='txt',
                            max_records_in_file=1)

    dev_raw_data_source >> local_fs
    files_pipeline = builder.build('Generate files pipeline')
    sdc_executor.add_pipeline(files_pipeline)

    # generate some batches/files
    sdc_executor.start_pipeline(files_pipeline).wait_for_pipeline_batch_count(10)
    sdc_executor.stop_pipeline(files_pipeline)


@pytest.mark.parametrize('read_order', ['TIMESTAMP', 'LEXICOGRAPHICAL'])
@pytest.mark.parametrize('file_post_processing', ['DELETE', 'ARCHIVE'])
def test_directory_no_post_process_older_files(sdc_builder, sdc_executor, file_writer, shell_executor, list_dir,
                                               read_order, file_post_processing):
    """
    Test that only files that have been processed by the origin are post processed
    """

    FILES_DIRECTORY = '/tmp'

    random_str = get_random_string(string.ascii_letters, 10)
    file_path = os.path.join(FILES_DIRECTORY, random_str)
    archive_path = os.path.join(FILES_DIRECTORY, random_str + '_archive')

    # Create files and archive directories
    shell_executor(f"""
        mkdir {file_path}
        mkdir {archive_path}
    """)

    # Create files
    for i in range(4):
        file_writer(os.path.join(file_path, f'file-{i}.txt'), f'{i}')

    builder = sdc_builder.get_pipeline_builder()
    directory = builder.add_stage('Directory', type='origin')
    directory.set_attributes(data_format='TEXT',
                             file_name_pattern='file-*.txt',
                             file_name_pattern_mode='GLOB',
                             file_post_processing=file_post_processing,
                             archive_directory=archive_path,
                             files_directory=file_path,
                             process_subdirectories=True,
                             read_order=read_order,
                             first_file_to_process='file-2.txt')

    trash = builder.add_stage('Trash')

    pipeline_finisher = builder.add_stage('Pipeline Finisher Executor')
    pipeline_finisher.set_attributes(preconditions=['${record:eventType() == \'no-more-data\'}'],
                                     on_record_error='DISCARD')

    directory >> trash
    directory >= pipeline_finisher

    pipeline = builder.build(f'Test directory origin no postprocess older files {read_order} {file_post_processing}')
    sdc_executor.add_pipeline(pipeline)

    sdc_executor.start_pipeline(pipeline).wait_for_finished()

    unprocessed_files = [os.path.join(file_path, f'file-{i}.txt') for i in range(2)]
    assert sorted(list_dir('TEXT', file_path, 'file-*.txt', batches=2)) == unprocessed_files

    if file_post_processing == 'ARCHIVE':
        archived_files = [os.path.join(archive_path, f'file-{i}.txt') for i in range(2, 4)]
        assert sorted(list_dir('TEXT', archive_path, 'file-*.txt', batches=2)) == archived_files


def setup_avro_file(sdc_executor, tmp_directory):
    """Setup 5 avro records and save in local system. The pipelines looks like:

        dev_raw_data_source >> local_fs

    """
    avro_records = [
    {
        "name": "sdc1",
        "age": 3,
        "emails": ["sdc1@streamsets.com", "sdc@company.com"],
        "boss": {
            "name": "sdc0",
            "age": 3,
            "emails": ["sdc0@streamsets.com", "sdc1@apache.org"],
            "boss": None
        }
    },
    {
        "name": "sdc2",
        "age": 3,
        "emails": ["sdc0@streamsets.com", "sdc@gmail.com"],
        "boss": {
            "name": "sdc0",
            "age": 3,
            "emails": ["sdc0@streamsets.com", "sdc1@apache.org"],
            "boss": None
        }
    },
    {
        "name": "sdc3",
        "age": 3,
        "emails": ["sdc0@streamsets.com", "sdc@gmail.com"],
        "boss": {
            "name": "sdc0",
            "age": 3,
            "emails": ["sdc0@streamsets.com", "sdc1@apache.org"],
            "boss": None
        }
    },
    {
        "name": "sdc4",
        "age": 3,
        "emails": ["sdc0@streamsets.com", "sdc@gmail.com"],
        "boss": {
            "name": "sdc0",
            "age": 3,
            "emails": ["sdc0@streamsets.com", "sdc1@apache.org"],
            "boss": None
        }
    },
    {
        "name": "sdc5",
        "age": 3,
        "emails": ["sdc0@streamsets.com", "sdc@gmail.com"],
        "boss": {
            "name": "sdc0",
            "age": 3,
            "emails": ["sdc0@streamsets.com", "sdc1@apache.org"],
            "boss": None
        }
    }]

    avro_schema = {
        "type": "record",
        "name": "Employee",
        "fields": [
            {"name": "name", "type": "string"},
            {"name": "age", "type": "int"},
            {"name": "emails", "type": {"type": "array", "items": "string"}},
            {"name": "boss" ,"type": ["Employee", "null"]}
        ]
    }

    raw_data = ''.join(json.dumps(avro_record) for avro_record in avro_records)

    pipeline_builder = sdc_executor.get_pipeline_builder()
    dev_raw_data_source = pipeline_builder.add_stage('Dev Raw Data Source')
    dev_raw_data_source.set_attributes(data_format='JSON', raw_data=raw_data, stop_after_first_batch=True)
    local_fs = pipeline_builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='AVRO',
                            avro_schema_location='INLINE',
                            avro_schema=json.dumps(avro_schema),
                            directory_template=tmp_directory,
                            files_prefix='sdc-${sdc:id()}', files_suffix='txt', max_records_in_file=5)

    dev_raw_data_source >> local_fs
    files_pipeline = pipeline_builder.build('Generate files pipeline')
    sdc_executor.add_pipeline(files_pipeline)

    # generate some batches/files
    sdc_executor.start_pipeline(files_pipeline).wait_for_finished(timeout_sec=5)

    return avro_records


def setup_basic_dilimited_file(sdc_executor, tmp_directory):
    """Setup simple 3 csv records and save in local system. The pipelines looks like:

            dev_raw_data_source >> local_fs

    """
    csv_records = ["A,B", "c,d", "e,f"]
    return setup_dilimited_file(sdc_executor, tmp_directory, csv_records)


def setup_custom_delimited_file(sdc_executor, tmp_directory):
    """Setup 1 custom csv records and save in local system. The pipelines looks like:

            dev_raw_data_source >> local_fs

    """
    csv_records = ["A^!B !^$^A"]
    return setup_dilimited_file(sdc_executor, tmp_directory, csv_records)


def setup_long_dilimited_file(sdc_executor, tmp_directory):
    """Setup 10 csv records and some records contain long charsets
    and save in local system. The pipelines looks like:

            dev_raw_data_source >> local_fs

    """
    csv_records = [
        "a,b,c,d",
        "e,f,g,h",
        "aaa,bbb,ccc,ddd",
        "i,j,k,l",
        "aa1,bb1,cc1,dd1",
        "aa2,bb2,cc2,dd2",
        "m,n,o,p",
        "q,r,s,t",
        "aa3,bb3,cc3,dd3",
        "aa4,bb5,cc5,dd5"
    ]

    return setup_dilimited_file(sdc_executor, tmp_directory, csv_records)


def setup_dilimited_with_comment_file(sdc_executor, tmp_directory):
    """Setup 3 csv records and save in local system. The pipelines looks like:

            dev_raw_data_source >> local_fs

    """
    csv_records = [
        "a,b",
        "# This is comment",
        "c,d"
    ]

    return setup_dilimited_file(sdc_executor, tmp_directory, csv_records)


def setup_dilimited_with_empty_line_file(sdc_executor, tmp_directory):
    """Setup 3 csv records and save in local system. The pipelines looks like:

            dev_raw_data_source >> local_fs

    """
    csv_records = [
        "a,b",
        "",
        "c,d"
    ]

    return setup_dilimited_file(sdc_executor, tmp_directory, csv_records)


def setup_dilimited_file(sdc_executor, tmp_directory, csv_records):
    """Setup csv records and save in local system. The pipelines looks like:

            dev_raw_data_source >> local_fs

    """
    raw_data = "\n".join(csv_records)
    pipeline_builder = sdc_executor.get_pipeline_builder()
    dev_raw_data_source = pipeline_builder.add_stage('Dev Raw Data Source')
    dev_raw_data_source.set_attributes(data_format='TEXT', raw_data=raw_data, stop_after_first_batch=True)
    local_fs = pipeline_builder.add_stage('Local FS', type='destination')
    local_fs.set_attributes(data_format='TEXT',
                            directory_template=tmp_directory,
                            files_prefix='sdc-${sdc:id()}', files_suffix='csv')

    dev_raw_data_source >> local_fs
    files_pipeline = pipeline_builder.build('Generate files pipeline')
    sdc_executor.add_pipeline(files_pipeline)

    # generate some batches/files
    sdc_executor.start_pipeline(files_pipeline).wait_for_finished(timeout_sec=5)

    return csv_records


def read_csv_file(file_path, delimiter, remove_header=False):
    """ Reads a csv file with records separated by delimiter"""
    rows = []
    with open(file_path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=delimiter)
        for row in csv_reader:
            rows.append(row)
    if remove_header:
        rows = rows[1:]
    return rows
