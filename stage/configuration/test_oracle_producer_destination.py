import logging
import string


import pytest
import sqlalchemy
from streamsets.testframework.decorators import stub
from streamsets.testframework.markers import category, sdc_min_version
from streamsets.testframework.utils import get_random_string


logger = logging.getLogger(__name__)


pytestmark = [pytest.mark.sdc_min_version('3.15.0'), pytest.mark.database('oracle')]


@stub
@category('advanced')
def test_additional_jdbc_configuration_properties(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
@pytest.mark.parametrize('stage_attributes', [{'change_log_format': 'MSSQL'},
                                              {'change_log_format': 'MongoDBOpLog'},
                                              {'change_log_format': 'MySQLBinLog'},
                                              {'change_log_format': 'NONE'},
                                              {'change_log_format': 'OracleCDC'}])
def test_change_log_format(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('basic')
@pytest.mark.parametrize('stage_attributes', [{'encrypt_connection': True}])
def test_cipher_suites(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('advanced')
def test_connection_health_test_query(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
def test_connection_timeout_in_seconds(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
def test_data_sqlstate_codes(sdc_builder, sdc_executor, database):
    pass


@stub
@category('basic')
def test_database_host(sdc_builder, sdc_executor, database):
    pass


@stub
@category('basic')
def test_database_secure_port(sdc_builder, sdc_executor, database):
    pass


@stub
@category('basic')
def test_database_sid(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
@pytest.mark.parametrize('stage_attributes', [{'default_operation': 'DELETE'},
                                              {'default_operation': 'INSERT'},
                                              {'default_operation': 'UPDATE'}])
def test_default_operation(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('advanced')
@pytest.mark.parametrize('stage_attributes', [{'enclose_object_names': False}, {'enclose_object_names': True}])
def test_enclose_object_names(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('basic')
@pytest.mark.parametrize('stage_attributes', [{'encrypt_connection': False}, {'encrypt_connection': True}])
def test_encrypt_connection(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('advanced')
def test_field_to_column_mapping(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
def test_idle_timeout_in_seconds(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
def test_init_query(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
def test_jdbc_driver_class_name(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
def test_max_connection_lifetime_in_seconds(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
def test_maximum_pool_size(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
def test_minimum_idle_connections(sdc_builder, sdc_executor, database):
    pass


@stub
@category('basic')
@pytest.mark.parametrize('stage_attributes', [{'on_record_error': 'DISCARD'},
                                              {'on_record_error': 'STOP_PIPELINE'},
                                              {'on_record_error': 'TO_ERROR'}])
def test_on_record_error(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('basic')
def test_password(sdc_builder, sdc_executor, database):
    pass


@stub
@category('basic')
def test_preconditions(sdc_builder, sdc_executor, database):
    pass


@stub
@category('basic')
def test_required_fields(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
@pytest.mark.parametrize('stage_attributes', [{'rollback_batch_on_error': False}, {'rollback_batch_on_error': True}])
def test_rollback_batch_on_error(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('basic')
def test_schema_name(sdc_builder, sdc_executor, database):
    pass


@stub
@category('basic')
@pytest.mark.parametrize('stage_attributes', [{'encrypt_connection': True}])
def test_server_certificate_pem(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('basic')
@pytest.mark.parametrize('stage_attributes', [{'encrypt_connection': True, 'verify_hostname_': True}])
def test_ssl_distinguished_name(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('advanced')
@pytest.mark.parametrize('stage_attributes', [{'use_multi_row_operation': True}])
def test_statement_parameter_limit(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('basic')
def test_table_name(sdc_builder, sdc_executor, database):
    pass


@stub
@category('advanced')
@pytest.mark.parametrize('stage_attributes', [{'transaction_isolation': 'DEFAULT'},
                                              {'transaction_isolation': 'TRANSACTION_READ_COMMITTED'},
                                              {'transaction_isolation': 'TRANSACTION_READ_UNCOMMITTED'},
                                              {'transaction_isolation': 'TRANSACTION_REPEATABLE_READ'},
                                              {'transaction_isolation': 'TRANSACTION_SERIALIZABLE'}])
def test_transaction_isolation(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('advanced')
@pytest.mark.parametrize('stage_attributes', [{'unsupported_operation_handling': 'DISCARD'},
                                              {'unsupported_operation_handling': 'SEND_TO_ERROR'},
                                              {'unsupported_operation_handling': 'USE_DEFAULT'}])
def test_unsupported_operation_handling(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('advanced')
@pytest.mark.parametrize('stage_attributes', [{'use_multi_row_operation': False}, {'use_multi_row_operation': True}])
def test_use_multi_row_operation(sdc_builder, sdc_executor, database, stage_attributes):
    pass


@stub
@category('basic')
def test_username(sdc_builder, sdc_executor, database):
    pass


@stub
@category('basic')
@pytest.mark.parametrize('stage_attributes', [{'encrypt_connection': True, 'verify_hostname_': False},
                                              {'encrypt_connection': True, 'verify_hostname_': True}])
def test_verify_hostname_(sdc_builder, sdc_executor, database, stage_attributes):
    pass

