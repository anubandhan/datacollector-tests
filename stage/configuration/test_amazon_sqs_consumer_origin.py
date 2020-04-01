import pytest

from streamsets.testframework.decorators import stub


@stub
def test_access_key_id(sdc_builder, sdc_executor):
    pass


@stub
def test_connection_timeout(sdc_builder, sdc_executor):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'region': 'OTHER'}])
def test_endpoint(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'sqs_message_attribute_level': 'ALL'}])
def test_include_sqs_sender_attributes(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
def test_max_batch_size_in_messages(sdc_builder, sdc_executor):
    pass


@stub
def test_max_batch_wait_time_in_ms(sdc_builder, sdc_executor):
    pass


@stub
def test_max_threads(sdc_builder, sdc_executor):
    pass


@stub
def test_number_of_messages_per_request(sdc_builder, sdc_executor):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'on_record_error': 'DISCARD'},
                                              {'on_record_error': 'STOP_PIPELINE'},
                                              {'on_record_error': 'TO_ERROR'}])
def test_on_record_error(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
def test_poll_wait_time_in_seconds(sdc_builder, sdc_executor):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_proxy': True}])
def test_proxy_host(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_proxy': True}])
def test_proxy_password(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_proxy': True}])
def test_proxy_port(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_proxy': True}])
def test_proxy_user(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
def test_queue_name_prefixes(sdc_builder, sdc_executor):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'region': 'AP_NORTHEAST_1'},
                                              {'region': 'AP_NORTHEAST_2'},
                                              {'region': 'AP_NORTHEAST_3'},
                                              {'region': 'AP_SOUTHEAST_1'},
                                              {'region': 'AP_SOUTHEAST_2'},
                                              {'region': 'AP_SOUTH_1'},
                                              {'region': 'CA_CENTRAL_1'},
                                              {'region': 'CN_NORTHWEST_1'},
                                              {'region': 'CN_NORTH_1'},
                                              {'region': 'EU_CENTRAL_1'},
                                              {'region': 'EU_WEST_1'},
                                              {'region': 'EU_WEST_2'},
                                              {'region': 'EU_WEST_3'},
                                              {'region': 'OTHER'},
                                              {'region': 'SA_EAST_1'},
                                              {'region': 'US_EAST_1'},
                                              {'region': 'US_EAST_2'},
                                              {'region': 'US_GOV_WEST_1'},
                                              {'region': 'US_WEST_1'},
                                              {'region': 'US_WEST_2'}])
def test_region(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
def test_retry_count(sdc_builder, sdc_executor):
    pass


@stub
def test_secret_access_key(sdc_builder, sdc_executor):
    pass


@stub
def test_socket_timeout(sdc_builder, sdc_executor):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'sqs_message_attribute_level': 'ALL'},
                                              {'sqs_message_attribute_level': 'BASIC'},
                                              {'sqs_message_attribute_level': 'NONE'}])
def test_sqs_message_attribute_level(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_proxy': False}, {'use_proxy': True}])
def test_use_proxy(sdc_builder, sdc_executor, stage_attributes):
    pass

