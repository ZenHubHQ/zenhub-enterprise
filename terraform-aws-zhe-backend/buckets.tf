# TODO: Implement AWS API Signature Version 4
# resource "aws_kms_key" "bucket_key" {
#   description             = "This key is used to encrypt bucket objects"
#   deletion_window_in_days = 10
# }

resource "aws_s3_bucket" "zhe_files" {
  bucket        = "zenhub${var.env}-files-${random_string.random.result}"
  acl           = "private"
  force_destroy = var.bucket_force_destroy

  # FIX-ME : KMS decryption is not supported by the library in use
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        # kms_master_key_id = aws_kms_key.bucket_key.arn
        # TODO: Implement AWS API Signature Version 4
        # ! "When creating a presigned URL for an object encrypted using an AWS KMS CMK, you must explicitly specify Signature Version 4"
        sse_algorithm = "AES256" # "aws:kms"
      }
    }
  }

  tags = {
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_s3_bucket" "zhe_images" {
  bucket        = "zenhub${var.env}-images-${random_string.random.result}"
  acl           = "private"
  force_destroy = var.bucket_force_destroy

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        # kms_master_key_id = aws_kms_key.bucket_key.arn
        # TODO: Implement AWS API Signature Version 4
        # ! "When creating a presigned URL for an object encrypted using an AWS KMS CMK, you must explicitly specify Signature Version 4"
        sse_algorithm = "AES256" # "aws:kms"
      }
    }
  }

  tags = {
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

data "aws_vpc_endpoint" "eks_s3" {
  vpc_id       = var.vpc_id
  service_name = "com.amazonaws.us-west-2.s3"
}

resource "aws_s3_bucket_policy" "AllowReadFromVPCE" {
  bucket = aws_s3_bucket.zhe_images.id

  policy = <<POLICY
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ZHEAllowVPCEndpointLIST",
            "Principal": "*",
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": ["${aws_s3_bucket.zhe_images.arn}"],
            "Condition": {
              "StringEquals": {
                "aws:SourceVpce": "${data.aws_vpc_endpoint.eks_s3.id}"
              }
            }
        },
        {
            "Sid": "ZHEAllowVPCEndpointREAD",
            "Principal": "*",
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": ["${aws_s3_bucket.zhe_images.arn}/*"],
            "Condition": {
              "StringEquals": {
                "aws:SourceVpce": "${data.aws_vpc_endpoint.eks_s3.id}"
              }
            }
        }
    ]
}
POLICY
}

resource "aws_s3_bucket_policy" "AllowReadFromVPCEFiles" {
  bucket = aws_s3_bucket.zhe_files.id

  policy = <<POLICY
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ZHEAllowVPCEndpointLIST",
            "Principal": "*",
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": ["${aws_s3_bucket.zhe_files.arn}"],
            "Condition": {
              "StringEquals": {
                "aws:SourceVpce": "${data.aws_vpc_endpoint.eks_s3.id}"
              }
            }
        },
        {
            "Sid": "ZHEAllowVPCEndpointREAD",
            "Principal": "*",
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": ["${aws_s3_bucket.zhe_files.arn}/*"],
            "Condition": {
              "StringEquals": {
                "aws:SourceVpce": "${data.aws_vpc_endpoint.eks_s3.id}"
              }
            }
        }
    ]
}
POLICY
}
