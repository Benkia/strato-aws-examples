provider "aws" {
    version ="=2.13.0"
    access_key = "${var.access_key}"
    secret_key = "${var.secret_key}"


    endpoints {
        ec2 = "https://${var.symphony_ip}/api/v2/ec2"
        rds = "https://${var.symphony_ip}/api/v2/aws/rds"
    }

    insecure = "true"
    skip_metadata_api_check = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    # No importance for this value currently
    region = "us-east-1"
}
