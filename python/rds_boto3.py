import sys
import boto3
import time
import random
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



# Replace following parameters with your IP, credentials and parameters
CLUSTER_IP = '10.16.145.246'
AWS_ACCESS = '8a1f5f58870d4e62a19bc43bba130d76'
AWS_SECRET = '42ef36689be2456483cce18474cec7ec'
ENGINE_NAME = 'mysql'
ENGINE_VERSION = '5.6.00'
DB_INSTANCE_TYPE = 'm1.small'
DB_NAME = 'mysql_db'
DB_USER_NAME = 'db_user1'
DB_USER_PASSWORD = 'db_pass123'
run_index = '%03x' % random.randrange(2**12)


"""
This script shows and example of Boto3 RDS integration with Stratoscale Symphony.

The scenario:
    1. Describe engine versions
    2. Create DB parameters group
    3. Modify DB parameters group
    4. Reset DB parameters group
    5. Create DB Instance
    6. Create DB snapshot
    7. Restore DB snapshot
    8. Delete restored DB snapshot
        
This example was tested on versions:
- Symphony version 4.2.1
- boto3 1.4.7
"""


# Creating a RDS client connection to Symphony AWS Compatible region    
def create_rds_client():
    return boto3.Session.client(
            boto3.session.Session(),
            service_name="rds",
            region_name="symphony",
            endpoint_url="https://%s/api/v2/aws/rds/" % CLUSTER_IP,
            verify=False,
            aws_access_key_id=AWS_ACCESS,
            aws_secret_access_key=AWS_SECRET
            )


def get_db_param_grp_family(rds_client): 
    describe_eng_ver_response = rds_client.describe_db_engine_versions()
    if describe_eng_ver_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        eng_list = [engine for engine in describe_eng_ver_response['DBEngineVersions']
                    if engine['Engine'] == ENGINE_NAME and engine['EngineVersion'] == ENGINE_VERSION]
        assert len(eng_list) == 1, 'Cannot find engine'
        db_param_grp_family = eng_list[0]['DBParameterGroupFamily']
        print("Successfully described DB Engine Versions")
        return db_param_grp_family
    else:
        print("Couldn't describe DB Engine Versions")


def create_param_group(rds_client, group_family):
    param_group_name = 'test_param_grp_%s' % run_index
    create_db_params_response = rds_client.create_db_parameter_group(
            DBParameterGroupName=param_group_name,
            DBParameterGroupFamily=group_family,
            Description='Test DB Params Group %s' % run_index)
    # Check Create DB Params group returned successfully
    if create_db_params_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        print("Successfully created DB parameters group {0}".format(param_group_name))
        return param_group_name
    else:
        print("Couldn't create DB parameters group")


def print_db_param_value(rds_client, param_group_name, param_name):
    rsp = rds_client.describe_db_parameters(DBParameterGroupName=param_group_name)
    value = next(param['ParameterValue'] for param in rsp['Parameters'] if param['ParameterName'] == param_name)
    print("In group {0} value of {1} is {2}".format(param_group_name,param_name,value))

    
def modify_param_group(rds_client, param_group_name, param_name):
    modify_db_params_response = rds_client.modify_db_parameter_group(
            DBParameterGroupName=param_group_name,
            Parameters=
            [
                {
                    "ParameterName": "autocommit",
                    "ParameterValue": "false"
                },
                { 
                    "ParameterName": "binlog_cache_size",
                    "ParameterValue": "32769"
                }
            ]
        )
    # Check modify DB Params group returned successfully
    if modify_db_params_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        print("Successfully modify DB parameters group {0}".format(param_group_name))
        return print_db_param_value(rds_client,param_group_name,param_name)
    else:
        print("Couldn't modify DB parameters group")


# Reset parameter group
def reset_param_group(rds_client, param_group_name, param_name):
    reset_db_params_response = rds_client.reset_db_parameter_group(
            DBParameterGroupName=param_group_name,
            ResetAllParameters=True
            )
    # check reset DB Params group returned successfully
    if reset_db_params_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        print("Successfully reset DB parameters group {0}".format(param_group_name))
        return print_db_param_value(rds_client,param_group_name, param_name)
    else:
        print("Couldn't reset DB parameters group")


# Create DB instance
def create_db_instance(rds_client, param_group_name):
    db_instance_name = 'test_instance_db_%s' % run_index
    create_db_instance_response = rds_client.create_db_instance(
                                        DBInstanceIdentifier=db_instance_name,
                                        DBInstanceClass=DB_INSTANCE_TYPE,
                                        DBName=DB_NAME,
                                        Engine=ENGINE_NAME,
                                        EngineVersion=ENGINE_VERSION,
                                        MasterUsername=DB_USER_NAME,
                                        MasterUserPassword=DB_USER_PASSWORD,
                                        DBParameterGroupName=param_group_name)
    # check Create DB instance returned successfully
    if create_db_instance_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        print("Successfully create DB instance {0}".format(db_instance_name))
    else:
        print("Couldn't create DB instance")
    
    print("waiting for db instance {0} to become ready".format( db_instance_name))
    number_of_retries = 20
    db_success = False
    for i in xrange(number_of_retries):
        time.sleep(30)
        db_status = rds_client.describe_db_instances(DBInstanceIdentifier=db_instance_name)['DBInstances'][0]['DBInstanceStatus']
        if db_status == 'available':
            db_success = True
            print("DB instance {0} is ready".format(db_instance_name))
            return db_instance_name 
            break
        else:
            print("DB instance {0} is initializing. Attempt {1}".format(db_instance_name, i))
    assert db_success, "DB failed {0} to initialize".format(db_instance_name)


# Create DB snapshot
def create_db_snapshot(rds_client, db_instance_name):
    db_snapshot_name = 'test_snapshot_db_%s' % run_index
    create_db_snapshot_response = rds_client.create_db_snapshot(
                                        DBInstanceIdentifier=db_instance_name,
                                        DBSnapshotIdentifier=db_snapshot_name
                                        )
    # check Create DB instance returned successfully
    waiter = rds_client.get_waiter('db_snapshot_available')
    waiter.wait(
            DBSnapshotIdentifier=db_snapshot_name,
             WaiterConfig={
                 'Delay': 30,
                 'MaxAttempts': 70
                 }
            )
    print("DB snapshot {0} is ready".format(db_snapshot_name))
    return db_snapshot_name
    
# Restore DB snapshot_db
def restore_db_instance(rds_client, db_snapshot_name):
    db_restored_name = 'test_restored_snapshot_db_%s' % run_index
    restore_db_response = rds_client.restore_db_instance_from_db_snapshot(
                                                DBInstanceIdentifier=db_restored_name,
                                                DBSnapshotIdentifier=db_snapshot_name
                                            )
    # check restore DB instance returned successfully
    if restore_db_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        print("Successfully restored DB snapshot {0} to instance {1}".format(db_snapshot_name, db_restored_name))
    else:
        print("Couldn't restore DB snapshot")
    print("waiting for restored db {0} to become ready".format(db_instance_name))
    number_of_retries = 20
    restore_success = False
    for i in xrange(number_of_retries):
        time.sleep(30)
        restored_status = rds_client.describe_db_instances(DBInstanceIdentifier=db_restored_name)['DBInstances'][0]['DBInstanceStatus']
        if restored_status == 'available':
            restore_success = True
            print("Restored DB {0} is ready".format(db_restored_name))
            return db_restored_name
            break
        else:
            print("Restored DB {0} is initializing. Attempt {1}".format(db_restored_name, i))
    assert restore_success, "Restored {0} to initialize".format(db_restored_name)


# Delete restored DB
def delete_restores_db(rds_client, db_restored_name):
    del_restore_db_response = rds_client.delete_db_instance(
                                                DBInstanceIdentifier=db_restored_name,
                                            )
    # check delete DB instance returned successfully
    waiter=rds_client.get_waiter('db_instance_deleted')
    waiter.wait(DBInstanceIdentifier=db_restored_name)
    print("Restored DB {0} is deleted".format(db_restored_name))


def main():
    rds_client = create_rds_client()
    group_family = get_db_param_grp_family(rds_client)
    param_group_name = create_param_group(rds_client, group_family)
    param_name = 'binlog_cache_size'
    print_db_param_value(rds_client, param_group_name, param_name)
    modified_param_value = modify_param_group(rds_client, param_group_name, param_name)
    reset_param_group(rds_client, param_group_name, param_name)
    db_instance_name = create_db_instance(rds_client, param_group_name)
    db_restored_name = restore_db_instance(rds_client, db_snapshot_name)
    delete_restores_db(rds_client, db_restored_name)


if __name__ == '__main__':
    sys.exit(main())
