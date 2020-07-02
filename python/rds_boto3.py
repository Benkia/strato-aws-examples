import sys
import boto3
import time
import random
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



# Replace following parameters with your IP, credentials and parameters
CLUSTER_IP = '10.16.145.14'
AWS_ACCESS = 'f3e51bfe05954524809e80f629a08076'
AWS_SECRET = '6fc950da9c514d22a79c4346df590c09'
VPC_CIDR = '10.11.12.0/24'
VPC_NAME = 'DB_VPC'
SUBNET_CIDR = '10.11.12.0/24'
ENGINE_NAME = 'mysql'
ENGINE_VERSION = '5.6.00'
DB_INSTANCE_TYPE = 'db.m1.small'
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
- boto3 1.14.12
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


# Creating an EC2 client connection to Symphony AWS Compatible region  
def create_ec2_client():
    return boto3.Session.client(
            boto3.session.Session(),
            service_name="ec2",
            region_name="symphony",
            endpoint_url="https://%s/api/v2/aws/ec2/" % CLUSTER_IP,
            verify=False,
            aws_access_key_id=AWS_ACCESS,
            aws_secret_access_key=AWS_SECRET
            )


def create_vpc(client_ec2):
    vpc = client_ec2.create_vpc(CidrBlock=VPC_CIDR)
    vpcId = vpc['Vpc']['VpcId']
    waiter = client_ec2.get_waiter(waiter_name='vpc_available')
    waiter.wait(VpcIds=[vpcId, ])
    client_ec2.create_tags(
            Resources=[
                vpcId,
                ],
            Tags=[
                {
                    'Key': 'Name',
                    'Value': VPC_NAME
                },
            ]
        )
    print('Created VPC with ID:{0}'.format(vpcId))
    return vpcId


def create_gateway(client_ec2):
    igw = client_ec2.create_internet_gateway()
    if igw['ResponseMetadata']['HTTPStatusCode'] == 200:
        igwId = igw['InternetGateway']['InternetGatewayId']
        print('Created InternetGateway with ID:{0}'.format(igwId))
        return igwId
    else:
        print('Create InternetGateway failed')


def attach_gateway_to_vpc(client_ec2, vpcId, igwId):
    attach_gateway = client_ec2.attach_internet_gateway(
        InternetGatewayId=igwId,
        VpcId=vpcId
    )
    if attach_gateway['ResponseMetadata']['HTTPStatusCode'] == 200:
        print("Attached InternetGateway with ID: {0} to VPC {1} " .format(
            igwId,
            vpcId
        ))
        client_ec2.create_tags(
                Resources=[
                igwId,
                ],
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': 'DB_IGW'
                    },
                ]
            )
    else:
        print('Create InternetGateway failed')


def create_subnet(client_ec2, vpcId):
    subnet = client_ec2.create_subnet(CidrBlock=SUBNET_CIDR, VpcId=vpcId)
    subnetId = subnet['Subnet']['SubnetId']
    waiter = client_ec2.get_waiter('subnet_available')
    waiter.wait(SubnetIds=[subnetId, ])
    client_ec2.create_tags(
            Resources=[
                subnetId,
            ],
            Tags=[
                {
                    'Key': 'Name',
                    'Value': 'DB_Subnet'
                    },
                ]
            )
    print('Created subnet with ID:{0} '.format(subnetId))
    return subnetId


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


# Create DB subnet group
def create_db_subnet_group(rds_client, subnetId):
    db_subnet_group_name= 'subnet_group_db_%s' % run_index
    db_subnet_group = rds_client.create_db_subnet_group(
            DBSubnetGroupName=db_subnet_group_name,
            DBSubnetGroupDescription='DataBaseSubnetGroup',
            SubnetIds=[
                subnetId
            ],
    )
    if  db_subnet_group['ResponseMetadata']['HTTPStatusCode'] == 200:
        print("Successfully create DB subnet group {0}".format(db_subnet_group_name))
        return db_subnet_group_name 
    else:
        print("Couldn't create DB subnet group")


# Create DB instance
def create_db_instance(rds_client, param_group_name, db_subnet_group_name):
    db_instance_name = 'test_instance_db_%s' % run_index
    db_instance_response = rds_client.create_db_instance(
                                        DBInstanceIdentifier=db_instance_name,
                                        DBInstanceClass=DB_INSTANCE_TYPE,
                                        DBName=DB_NAME,
                                        DBSubnetGroupName=db_subnet_group_name,
                                        Engine=ENGINE_NAME,
                                        EngineVersion=ENGINE_VERSION,
                                        MasterUsername=DB_USER_NAME,
                                        MasterUserPassword=DB_USER_PASSWORD,
                                        DBParameterGroupName=param_group_name)
    # check Create DB instance returned successfully
    db_instance_id = db_instance_response['DBInstance']['DBInstanceIdentifier']
    waiter = rds_client.get_waiter('db_instance_available')
    waiter.wait(
            DBInstanceIdentifier=db_instance_id,
            WaiterConfig={
                 'Delay': 50,
                 'MaxAttempts': 100
                 }
            )
    print("Successfully create DB instance {0}".format(db_instance_name))
    return db_instance_id


# Create DB snapshot
def create_db_snapshot(rds_client, db_instance_id):
    db_snapshot_name = 'test_snapshot_db_%s' % run_index
    db_snapshot_response = rds_client.create_db_snapshot(
                                        DBInstanceIdentifier=db_instance_id,
                                        DBSnapshotIdentifier=db_snapshot_name
                                        )
    db_snapshot_id = db_snapshot_response['DBSnapshot']['DBSnapshotIdentifier']
    # check Create DB instance returned successfully
    waiter = rds_client.get_waiter('db_snapshot_available')
    waiter.wait(DBInstanceIdentifier=db_snapshot_id)
    print("DB snapshot {0} is ready".format(db_snapshot_name))
    return db_snapshot_id

   # if db_snapshot_response['ResponseMetadata']['HTTPStatusCode'] == 200:
   #     print("DB snapshot {0} is ready".format(db_snapshot_name))
     #   return db_snapshot_id
   # else:
    #    print("Couldn't create DB snapshot")
   

# Restore DB snapshot_db
def restore_db_instance(rds_client, db_snapshot_id, db_subnet_group_name):
    db_restore_name = 'test_restored_snapshot_db_%s' % run_index
    restore_db_response = rds_client.restore_db_instance_from_db_snapshot(
                                                DBInstanceIdentifier=db_restore_name,
                                                DBSnapshotIdentifier=db_snapshot_id,
                                                DBSubnetGroupName=db_subnet_group_name
                                            )
    db_restored_id =  restore_db_response['DBInstance']['DBInstanceIdentifier']
    # check restore DB instance returned successfully
    waiter = rds_client.get_waiter('db_instance_available')
    waiter.wait(
    DBInstanceIdentifier=db_restored_id
    )
    print("Successfully restored DB snapshot {0} to instance {1}".format(db_snapshot_id, db_restored_id))
    return db_restored_id


# Delete restored DB
def delete_restored_db(rds_client, db_restored_id):
    del_restored_db_response = rds_client.delete_db_instance(
                                                DBInstanceIdentifier=db_restored_id,
                                                SkipFinalSnapshot=True,
                                                DeleteAutomatedBackups=True
                                            )
    # check delete DB instance returned successfully
    waiter=rds_client.get_waiter('db_instance_deleted')
    print("waiting RDS instance {} deleted ...".format(db_restored_id))
    waiter.wait(
            DBInstanceIdentifier=db_restored_id
            )
    print("Restored DB {0} is deleted".format(db_restored_id))


def main():
    import ipdb
    ipdb.set_trace()
    rds_client = create_rds_client()
    client_ec2 = create_ec2_client()
    vpcId = create_vpc(client_ec2)
    igwId = create_gateway(client_ec2)
    attach_gateway_to_vpc(client_ec2, vpcId, igwId)
    subnetId = create_subnet(client_ec2, vpcId)
    group_family = get_db_param_grp_family(rds_client)
    param_group_name = create_param_group(rds_client, group_family)
    param_name = 'binlog_cache_size'
    print_db_param_value(rds_client, param_group_name, param_name)
    modified_param_value = modify_param_group(rds_client, param_group_name, param_name)
    reset_param_group(rds_client, param_group_name, param_name)
    db_subnet_group_name =  create_db_subnet_group(rds_client, subnetId)
    db_instance_id = create_db_instance(rds_client, param_group_name, db_subnet_group_name)
    db_snapshot_id = create_db_snapshot(rds_client , db_instance_id)
    db_restored_id = restore_db_instance(rds_client, db_snapshot_id, db_subnet_group_name)
    delete_restored_db(rds_client, db_restored_id)


if __name__ == '__main__':
    sys.exit(main())
