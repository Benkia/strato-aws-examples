###################################
# Creating a VPC & Networking
###################################

resource "aws_vpc" "spark-vpc" {
  cidr_block         = "172.21.0.0/16"
  enable_dns_support = true

  tags = {
    Name = "spark Example VPC"
  }
}

resource "aws_subnet" "subnet1" {
  cidr_block = "172.21.1.0/24"
  vpc_id     = aws_vpc.spark-vpc.id

  tags = {
    Name = "spark Example web subnet"
  }
}

# add dhcp options
resource "aws_vpc_dhcp_options" "dns_resolver" {
  domain_name_servers = ["8.8.8.8", "8.8.4.4"]
}

# associate dhcp with vpc
resource "aws_vpc_dhcp_options_association" "dns_resolver" {
  vpc_id          = aws_vpc.spark-vpc.id
  dhcp_options_id = aws_vpc_dhcp_options.dns_resolver.id
}

# create igw
resource "aws_internet_gateway" "app_igw" {
  vpc_id = aws_vpc.spark-vpc.id
}

#new default route table with igw association 
resource "aws_default_route_table" "default" {
  default_route_table_id = aws_vpc.spark-vpc.default_route_table_id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.app_igw.id
  }
}

###################################
# Cloud init data
data "template_file" "centosconfig" {
  template = file("./centosconfig.cfg")
}

data "template_file" "spark-master-init" {
  template = file("./spark-master-init.sh")
}

data "template_file" "spark-worker-init" {
  template = file("./spark-worker-init.sh")

  vars = {
    master_ip = aws_instance.spark-masters[0].private_ip
  }
}

data "template_cloudinit_config" "spark_master_config" {
  gzip          = false
  base64_encode = false

  part {
    filename     = "centosconfig.cfg"
    content_type = "text/cloud-config"
    content      = data.template_file.centosconfig.rendered
  }
  part {
    filename     = "spark-master-init.sh"
    content_type = "text/x-shellscript"
    content      = data.template_file.spark-master-init.rendered
  }
}

data "template_cloudinit_config" "spark_worker_config" {
  gzip          = false
  base64_encode = false

  part {
    filename     = "centosconfig.cfg"
    content_type = "text/cloud-config"
    content      = data.template_file.centosconfig.rendered
  }
  part {
    filename     = "spark-worker-init.sh"
    content_type = "text/x-shellscript"
    content      = data.template_file.spark-worker-init.rendered
  }
}
###################################

resource "aws_key_pair" "app_keypair" {
  public_key = file(var.public_keypair_path)
  key_name   = "wp_app_kp"
}

# Creating two instances of web server ami with cloudinit
resource "aws_instance" "spark-masters" {
  ami           = var.ami_spark_node
  instance_type = var.spark_masters_type
  subnet_id     = aws_subnet.subnet1.id
  key_name      = aws_key_pair.app_keypair.key_name

  vpc_security_group_ids = [aws_security_group.spark-sec.id, aws_security_group.allout.id]
  user_data              = data.template_cloudinit_config.spark_master_config.rendered

  tags = {
    Name = "Spark-master-${count.index}"
  }

  count = var.spark_masters_number
}

resource "aws_eip" "spark_master_eips" {
  vpc             = true
  count           = var.spark_masters_number
}

resource "aws_eip_association" "spark_master_eip_assoc" {
  allocation_id = aws_eip.spark_master_eips[count.index].id
  instance_id   = aws_instance.spark-masters[count.index].id
  count         = var.spark_masters_number
}

# Creating two instances of web server ami with cloudinit
resource "aws_instance" "spark-workers" {
  ami           = var.ami_spark_node
  instance_type = var.spark_workers_type
  subnet_id     = aws_subnet.subnet1.id
  key_name      = aws_key_pair.app_keypair.key_name

  vpc_security_group_ids = [aws_security_group.spark-sec.id, aws_security_group.allout.id]
  user_data              = data.template_cloudinit_config.spark_worker_config.rendered

  tags = {
    Name = "Spark-worker-${count.index}"
  }

  count = var.spark_workers_number
}

resource "aws_eip" "spark_worker_eips" {
  vpc             = true
  count           = var.spark_workers_number
}

resource "aws_eip_association" "spark_worker_eip_assoc" {
  allocation_id = aws_eip.spark_worker_eips[count.index].id
  instance_id   = aws_instance.spark-workers[count.index].id
  count         = var.spark_workers_number
}
##################################
# Security group definitions
# Web server sec group

resource "aws_security_group" "spark-sec" {
  name   = "spark-secgroup"
  vpc_id = aws_vpc.spark-vpc.id

  # Spark UI
  ingress {
    from_port   = 4040
    to_port     = 4040
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Spark Master UI
  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Spark Master UI
  ingress {
    from_port   = 7077
    to_port     = 7077
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Jupyter
  ingress {
    from_port   = 8888
    to_port     = 8888
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  #ssh from anywhere (for debugging)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # ping access from anywhere
  ingress {
    from_port   = 8
    to_port     = 0
    protocol    = "icmp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

#public access sg 
# allow all egress traffic (needed for server to download packages)
resource "aws_security_group" "allout" {
  name   = "allout-secgroup"
  vpc_id = aws_vpc.spark-vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# LB Sec group definition 
resource "aws_security_group" "lb-sec" {
  name   = "lb-secgroup"
  vpc_id = aws_vpc.spark-vpc.id

  # Spark UI
  ingress {
    from_port   = 4040
    to_port     = 4040
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Jupyter
  ingress {
    from_port   = 8888
    to_port     = 8888
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  #ping from anywhere
  ingress {
    from_port   = 8
    to_port     = 0
    protocol    = "icmp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

##################################

# Creating and attaching the load balancer
# to make LB internal (no floating IP) set internal to true
resource "aws_alb" "spark" {
  name               = "web-spark"
  subnets            = [aws_subnet.subnet1.id]
  internal           = false
  security_groups    = [aws_security_group.lb-sec.id]
  load_balancer_type = "application"
}

##### ALB Spark UI ###############
resource "aws_alb_target_group" "spark_ui_tg" {
  port     = 4040
  protocol = "HTTP"
  vpc_id   = aws_vpc.spark-vpc.id
}

resource "aws_alb_target_group_attachment" "spark_ui_attach_spark_nodes" {
  target_group_arn = aws_alb_target_group.spark_ui_tg.arn
  target_id        = aws_instance.spark-masters[count.index].id
  port             = 4040
  count            = var.spark_masters_number
}

resource "aws_alb_listener" "spark_ui_listener" {
  default_action {
    target_group_arn = aws_alb_target_group.spark_ui_tg.arn
    type             = "forward"
  }
  load_balancer_arn = aws_alb.spark.arn
  port              = 4040
}

##### ALB Jupyter ###############
resource "aws_alb_target_group" "jupyter_tg" {
  port     = 8888
  protocol = "HTTP"
  vpc_id   = aws_vpc.spark-vpc.id
}

resource "aws_alb_target_group_attachment" "jupyter_attach_spark_nodes" {
  target_group_arn = aws_alb_target_group.jupyter_tg.arn
  target_id        = aws_instance.spark-masters[count.index].id
  port             = 8888
  count            = var.spark_masters_number
}

resource "aws_alb_listener" "jupyter_listener" {
  default_action {
    target_group_arn = aws_alb_target_group.jupyter_tg.arn
    type             = "forward"
  }
  load_balancer_arn = aws_alb.spark.arn
  port              = 8888
}

############ outputs ###########################

output "master-eips" {
  value = zipmap(aws_instance.spark-masters[*].private_ip,aws_eip.spark_master_eips[*].public_ip)
}

output "worker-eips" {
  value = zipmap(aws_instance.spark-workers[*].private_ip,aws_eip.spark_worker_eips[*].public_ip)
}
