# Region Credentials
variable "symphony_ip" {}
variable "secret_key" {}
variable "access_key" {}

# Main variables
variable "public_keypair_path" {}

variable "ami_spark_node" {}

variable "spark_masters_number" {
  default = 1
}
variable "spark_masters_type" {
  default = "t2.medium"
}

variable "spark_workers_number" {
  default = 1
}
variable "spark_workers_type" {
  default = "t2.medium"
}
