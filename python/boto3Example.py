import boto3
import sys
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


"""
    This script shows and example of Boto3 integration with Stratoscale Symphony.

    The scenario is as such:
        1. Instantiate an instance from an AMI,
        2. Create a 20 GB volume,
        3. Attach the volume to the created AMI.

    This example was tested on versions:
    - Symphony version 4.2.1
    - boto3 1.14.12
"""


# Replace following parameters with your IP and credentials
CLUSTER_IP = '<API endpoint IP>'
AWS_ACCESS = '<AWS Access Key ID>'
AWS_SECRET = '<AWS Secret Access Key>'


# Creating a connection to Symphony AWS Compatible region
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
    

# Finding our Centos image, grabbing its image ID
def import_centos_image(client):
    images = client.describe_images()
    image_id = next(image['ImageId'] for image in images['Images'] if 'centos' in image['Tags'][0]['Value'])
    waiter = client.get_waiter('image_available')
    waiter.wait(ImageIds=[image_id,])
    print("Found desired image with ID:{0}".format(image_id))
    return image_id


# Running a new instance using our Centos image ID
def run_instance(client, image_id):
    ec2_instance = client.run_instances(
        ImageId=image_id,
        MinCount=1,
        MaxCount=1
    )
    instance_id = ec2_instance['Instances'][0]['InstanceId']
    # check if EC2 instance was created successfully
    waiter = client.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id,])
    client.create_tags(
            Resources=[
                instance_id,
                ],
            Tags=[
                {
                    'Key': 'Name',
                    'Value': 'Centos_instance'
                },
            ]
        )
    print("Successfully created instance!{0} ".format(instance_id))
    return instance_id


# Create an EBS volume, 20G size
def create_ebs_volume(client):
    ebs_vol = client.create_volume(
        Size=20,
        AvailabilityZone='symphony'
        )
    volume_id = ebs_vol['VolumeId']
    # check that the EBS volume had been created successfully
    waiter = client.get_waiter('volume_available')
    waiter.wait(VolumeIds=[volume_id,])
    client.create_tags(
            Resources=[
                volume_id,
                ],
            Tags=[
                {
                    'Key': 'Name',
                    'Value': 'centos_volume'
                },
            ]
        )
    print("Successfully created Volume!{0} ".format(volume_id))
    return volume_id


# Attaching EBS volume to our EC2 instance
def attach_ebs(client, instance_id, volume_id):
    attach_resp = client.attach_volume(
        VolumeId=volume_id,
        InstanceId=instance_id,
        Device='/dev/sdm'
        )
    print("Attached EBS: {0} to instance {1}:" .format(volume_id,instance_id))


def main():
    client = create_ec2_client()
    image_id = import_centos_image(client)
    instance_id = run_instance(client, image_id)
    volume_id = create_ebs_volume(client)
    attach_ebs(client, instance_id, volume_id)


if __name__ == '__main__':
    sys.exit(main())
