import boto3
import sys
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Replace following parameters with your IP, credentials and parameters
CLUSTER_IP = '10.16.145.126'
AWS_ACCESS = '1cceed78ee5b471c9f2d9de5461c4e57'
AWS_SECRET = '3bb86e0dbae14584bfcbe522ab52e102'
VPC_CIDR = '10.11.12.0/24'
VPC_NAME = 'my_vpc'
SUBNET_CIDR = '10.11.12.0/24'
SECURITY_GROUP_NAME = 'SG'
IMAGE_SOURCE = 'https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-disk1.img'
LOAD_BALANCER_NAME = 'LB'
KEY_PAIR_PATH = os.path.dirname(os.path.realpath(__file__))


"""
This script shows and example of Boto3 ELB v2 integration with Stratoscale Symphony.

The scenario:
    1. Create VPC
    2. Create Internet-Gateway
    3. Attach Internet-Gateway
    4. Create Subnet
    5. Create Route-Table
    6. Associate Route-Table to Subnet
    7. Create Route
    8. Create Security-Group
    9. Create Key-Pairs
    10. Import Ubuntu image
    11. Run target instances with web-server
    12. Associate EIP 
    13. Create Load-Balancer 
    14. Create target-group
    15. Create Listener
    16. Register instances to target-group
    
This example was tested on versions:
    - Symphony version 4.2.1
    - boto3 1.14.12
"""


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


def create_elb_client():
    return boto3.Session.client(
            boto3.session.Session(),
            service_name="elbv2",
            region_name="symphony",
            endpoint_url="https://%s/api/v2/aws/elb/" % CLUSTER_IP,
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
    sys.exit(1)


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
                        'Value': 'MyIGW'
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
                    'Value': 'MySubnet'
                    },
                ]
            )
    print('Created subnet with ID:{0} '.format(subnetId))
    return subnetId


def create_route_table(client_ec2, vpcId):
    route_table = client_ec2.create_route_table(VpcId=vpcId)
    route_table_Id = route_table['RouteTable']['RouteTableId']
    if route_table['ResponseMetadata']['HTTPStatusCode'] == 200:
        client_ec2.create_tags(
                Resources=[
                    route_table_Id,
                ],
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': 'MyRouteTable'
                    },
                ]
            )
        print('Created Route Table ID: {0} in VPC: {1}'.format(
            route_table_Id,
            vpcId
        ))
        return route_table_Id
    else:
        print('Create route-tables failed')


def associate_rtb(client_ec2, route_table_Id, subnetId, igwId):
    associate_rtb = client_ec2.associate_route_table(
        RouteTableId=route_table_Id,
        SubnetId=subnetId,
        GatewayId=igwId
    )
    if associate_rtb['ResponseMetadata']['HTTPStatusCode'] == 200:
        print('Associated route table: {0} to subnet: {1}'.format(
            route_table_Id,
            subnetId
        ))
    else:
        print('Associated route table failed')


def create_route(client_ec2, igwId, route_table_Id, vpcId):
    route = client_ec2.create_route(
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=igwId,
        RouteTableId=route_table_Id
    )
    if route['ResponseMetadata']['HTTPStatusCode'] == 200:
        print('Created routing rule VPC with ID: {0}'.format(vpcId))
    else:
        print('Create routing rule failed')


def create_security_group(client_ec2, vpcId):
    security_group = client_ec2.create_security_group(
        Description='System test boto3',
        GroupName=SECURITY_GROUP_NAME,
        VpcId=vpcId
    )
    sgId = security_group['GroupId']
    waiter = client_ec2.get_waiter('security_group_exists')
    waiter.wait(GroupIds=[sgId, ])
    print('Created security-group with ID: {0}'.format(sgId))
    return sgId


# icmp and tcp protocols
def allow_ingress_rules(client_ec2, sgId):
    ingress = client_ec2.authorize_security_group_ingress(
        GroupId=sgId,
        IpPermissions=[
            {
                "IpProtocol": "icmp",
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 80,
                "ToPort": 80,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            }
        ]
    )
    if ingress['ResponseMetadata']['HTTPStatusCode'] == 200:
        print('Allow security group ingress for TCP')
    else:
        print('Allow security group ingress failed')


def allow_egress_rules(client_ec2, sgId):
    egress = client_ec2.authorize_security_group_egress(
        GroupId=sgId,
        IpPermissions=[
            {
                "IpProtocol": "icmp",
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 80,
                "ToPort": 80,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            }
        ]
    )
    if egress['ResponseMetadata']['HTTPStatusCode'] == 200:
        print('Allow security group egress for TCP')
    else:
        print('Allow security group egress failed')


def allow_egress_rules(client_ec2, sgId):
    egress = client_ec2.authorize_security_group_egress(
        GroupId=sgId,
        IpPermissions=[
            {
                "IpProtocol": "icmp",
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 80,
                "ToPort": 80,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
            }
        ]
    )
    if egress['ResponseMetadata']['HTTPStatusCode'] == 200:
        print('Allow security group egress for TCP')
    else:
        print('Allow security group egress failed')


def create_key_pair(client_ec2):
    key_pair = client_ec2.create_key_pair(KeyName='my_key')
    key_name = key_pair['KeyName']
    #key_file = os.path.expanduser('~/.ssh/{0}.pem'.format(key_name))
    key_file = os.path.expanduser('{path}/{key_name}.pem'.format(
        path=KEY_PAIR_PATH,
        key_name=key_name
    ))
    with open(key_file, "w") as key_file_out:
        key_file_out.write(key_pair['KeyMaterial'])
    waiter = client_ec2.get_waiter('key_pair_exists')
    waiter.wait(KeyNames=[key_name, ])
    print('Created key-pair for the instance with the name: {0}'.format(
        key_name
    ))
    return key_name


def import_image(client_ec2):
    image = client_ec2.import_image(
        DiskContainers=[{'Url': IMAGE_SOURCE}]
    )
    imageId = image['ImageId']
    waiter = client_ec2.get_waiter('image_available')
    waiter.wait(ImageIds=[imageId, ])
    print('Imported image with ID:{0} '.format(imageId))
    client_ec2.create_tags(
            Resources=[
                imageId,
                ],
            Tags=[
                {
                    'Key': 'Name',
                    'Value': 'Ubuntu'
                },
            ]
        )
    return imageId


def run_instance(client_ec2, imageId, key_name, subnetId, sgId, instance_name):
    userdata_read = open('./userdata.sh')
    userdata = userdata_read.read()
    userdata_read.close()
    instance = client_ec2.run_instances(
        ImageId=imageId,
        KeyName=key_name,
        MinCount=1,
        MaxCount=1,
        SubnetId=subnetId,
        SecurityGroupIds=[sgId],
        UserData=userdata
    )
    instanceId = instance['Instances'][0]['InstanceId']
    waiter = client_ec2.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instanceId, ])
    client_ec2.create_tags(
            Resources=[
                instanceId,
                ],
            Tags=[
                {
                    'Key': 'Name',
                    'Value': instance_name
                },
            ]
        )
    print ('Successfully created instance!{0}'.format(instanceId))
    return instanceId


def associate_eip(client_ec2, instanceId):
    allocate = client_ec2.allocate_address(Domain='vpc')
    associate_address = client_ec2.associate_address(
        AllocationId=allocate['AllocationId'],
        InstanceId=instanceId,
        PublicIp=allocate['PublicIp']
        )
    if associate_address['ResponseMetadata']['HTTPStatusCode'] == 200:
        allocationId = allocate['AllocationId']
        print('Associated allocation:{0} to instance: {1}'.format(
            allocationId, instanceId
        ))
    else:
        print('Associated EIP failed')


def create_lb(client_elb, subnetId, sgId):
    lb = client_elb.create_load_balancer(
            Name=LOAD_BALANCER_NAME,
            Subnets=[subnetId],
            SecurityGroups=[sgId],
            Scheme='internet-facing'
            )
    lbId = lb['LoadBalancers'][0]['LoadBalancerArn']
    waiter = client_elb.get_waiter('load_balancer_available')
    waiter.wait(LoadBalancerArns=[lbId, ],)
    print ('Successfully created load balancer {0}'.format(lbId))
    return lbId


def create_target_group(client_elb, vpcId):
    target_group = client_elb.create_target_group(
            Name='MyTargetGroup',
            Protocol='HTTP',
            Port=80,
            VpcId=vpcId
            )
    if target_group['ResponseMetadata']['HTTPStatusCode'] == 200:
        tgId = target_group['TargetGroups'][0]['TargetGroupArn']
        print ('Successfully created target group {0}'.format(tgId))
        return tgId
    else:
        print('Create target group failed')


def create_listener(client_elb, lbId, tgId):
    listener = client_elb.create_listener(
            LoadBalancerArn=lbId,
            Protocol='HTTP',
            Port=80,
            DefaultActions=[
                {
                    'Type': 'forward',
                    'TargetGroupArn': tgId
                }
            ]
        )
    if listener['ResponseMetadata']['HTTPStatusCode'] == 200:
        print ('Successfully created listener')
    else:
        print ('Create listener failed')

#def register_targets(client_elb, tgId, instanceId_1, instanceId_2, lbId):
#def register_targets(client_elb, lbId, tgId, targetsIds):
def register_targets(client_elb, lbId, tgId, targetId, **kwargs):
    targets = [
        {
            'Id': targetId,
        }
    ]
    if bool(kwargs):
        for target in kwargs.values():
            targets.append(
                {
                    'Id': target
                }
            )
    register_targets = client_elb.register_targets(
            TargetGroupArn=tgId,
            Targets=targets
        )
    waiter = client_elb.get_waiter('load_balancer_available')
    waiter.wait(LoadBalancerArns=[lbId, ],)
    print ('Successfully registered targets')


def main():
    import ipdb
    ipdb.set_trace()
    client_ec2 = create_ec2_client()
    client_elb = create_elb_client()
    vpcId = create_vpc(client_ec2)
    igwId = create_gateway(client_ec2)
    attach_gateway_to_vpc(client_ec2, vpcId, igwId)
    subnetId = create_subnet(client_ec2, vpcId)
    route_table_Id = create_route_table(client_ec2, vpcId)
    associate_rtb(client_ec2, route_table_Id, subnetId, igwId)
    create_route(client_ec2, igwId, route_table_Id, vpcId)
    sgId = create_security_group(client_ec2, vpcId)
    allow_ingress_rules(client_ec2, sgId)
    allow_egress_rules(client_ec2, sgId)
    key_name = create_key_pair(client_ec2)
    imageId = import_image(client_ec2)
    print('Starting to run target instances')
    instanceId_1 = run_instance(
        client_ec2,
        imageId,
        key_name,
        subnetId,
        sgId,
        'MyInstance1'
    )
    instanceId_2 = run_instance(
        client_ec2,
        imageId,
        key_name,
        subnetId,
        sgId,
        'MyInstance2'
    )
    associate_eip(client_ec2, instanceId_1)
    associate_eip(client_ec2, instanceId_2)
    lbId = create_lb(client_elb, subnetId, sgId)
    tgId = create_target_group(client_elb, vpcId)
    create_listener(client_elb, lbId, tgId)
    import ipdb
    ipdb.set_trace()
    register_targets(
        client_elb,
        lbId,
        tgId,
        instanceId_1,
        instatce2=instanceId_2
    )
    instanceId_3 = run_instance(
        client_ec2,
        imageId,
        key_name,
        subnetId,
        sgId,
        'MyInstance3'
    )
    register_targets(client_elb, lbId, tgId, instanceId_3)


if __name__ == '__main__':
    sys.exit(main())
