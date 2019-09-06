# .tfvars Sample File

# Region Credentials
symphony_ip = "10.16.146.31"
access_key = "b551721410d14f2aa75e47dacdfa841c"
secret_key = "4ba5d7f63f644806a672ea0cb1de691c"

# Recommend use of Xenial's latest cloud image
# located here: https://cloud.centos.org/centos/7/images/CentOS-7-x86_64-GenericCloud.qcow2

ami_spark_node = "ami-b108b2b2fc9e475586734ccf149772c1"
public_keypair_path = "/Users/liaz/work/sandbox/keypairs/liaz_prv.pub"

# optional
spark_workers_number = 2
# spark_workers_type = <number of instances>