import pytest

from streamsets.testframework.decorators import stub


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_default_cipher_suites': False, 'use_tls': True}])
def test_cipher_suites(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
def test_control_hub_base_url(sdc_builder, sdc_executor):
    pass


@stub
def test_control_hub_user_name(sdc_builder, sdc_executor):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'run_in_background': False}])
def test_delay_between_state_checks(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'instance_name_suffix': 'COUNTER', 'job_template': True},
                                              {'instance_name_suffix': 'PARAM_VALUE', 'job_template': True},
                                              {'instance_name_suffix': 'TIME_STAMP', 'job_template': True}])
def test_instance_name_suffix(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'job_template': False}, {'job_template': True}])
def test_job_template(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'job_template': True}])
def test_job_template_id(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'job_template': False}])
def test_jobs(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_tls': True}])
def test_keystore_file(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_tls': True}])
def test_keystore_key_algorithm(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_tls': True}])
def test_keystore_password(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'keystore_type': 'JKS', 'use_tls': True},
                                              {'keystore_type': 'PKCS12', 'use_tls': True}])
def test_keystore_type(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'on_record_error': 'DISCARD'},
                                              {'on_record_error': 'STOP_PIPELINE'},
                                              {'on_record_error': 'TO_ERROR'}])
def test_on_record_error(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'instance_name_suffix': 'PARAM_VALUE', 'job_template': True}])
def test_parameter_name(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
def test_password(sdc_builder, sdc_executor):
    pass


@stub
def test_preconditions(sdc_builder, sdc_executor):
    pass


@stub
def test_required_fields(sdc_builder, sdc_executor):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'job_template': False, 'reset_origin': False},
                                              {'job_template': False, 'reset_origin': True}])
def test_reset_origin(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'run_in_background': False}, {'run_in_background': True}])
def test_run_in_background(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'job_template': True}])
def test_runtime_parameters_for_each_instance(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_default_protocols': False, 'use_tls': True}])
def test_transport_protocols(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_tls': True}])
def test_truststore_file(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_tls': True}])
def test_truststore_password(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_tls': True}])
def test_truststore_trust_algorithm(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'truststore_type': 'JKS', 'use_tls': True},
                                              {'truststore_type': 'PKCS12', 'use_tls': True}])
def test_truststore_type(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_default_cipher_suites': False, 'use_tls': True},
                                              {'use_default_cipher_suites': True, 'use_tls': True}])
def test_use_default_cipher_suites(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_default_protocols': False, 'use_tls': True},
                                              {'use_default_protocols': True, 'use_tls': True}])
def test_use_default_protocols(sdc_builder, sdc_executor, stage_attributes):
    pass


@stub
@pytest.mark.parametrize('stage_attributes', [{'use_tls': False}, {'use_tls': True}])
def test_use_tls(sdc_builder, sdc_executor, stage_attributes):
    pass

