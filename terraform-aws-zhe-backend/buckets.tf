# TODO: Implement AWS API Signature Version 4
# resource "aws_kms_key" "bucket_key" {
#   description             = "This key is used to encrypt bucket objects"
#   deletion_window_in_days = 10
# }

resource "aws_s3_bucket" "private_files" {
  bucket        = "zenhub${var.env}-private-files-${random_string.random.result}"
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

resource "aws_s3_bucket" "public_images" {
  bucket        = "zenhub${var.env}-public-images-${random_string.random.result}"
  acl           = "public-read"
  force_destroy = var.bucket_force_destroy

  tags = {
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_s3_bucket_policy" "AllowPublicRead" {
  bucket = aws_s3_bucket.public_images.id

  policy = <<POLICY
{
    "Version": "2008-10-17",
    "Statement": [
        {
            "Sid": "AllowPublicRead",
            "Effect": "Allow",
            "Principal": {
                "AWS": "*"
            },
            "Action": "s3:GetObject",
            "Resource": "${aws_s3_bucket.public_images.arn}/*"
        }
    ]
}
POLICY
}
