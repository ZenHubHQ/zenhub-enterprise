data "aws_iam_policy_document" "zhe_buckets" {
  # TODO: Implement AWS API Signature Version 4
  # statement {
  #   sid    = "KMSAccess"
  #   effect = "Allow"
  #   actions = [
  #     "kms:GenerateDataKey",
  #     "kms:Decrypt"
  #   ]
  #   resources = [
  #     aws_kms_key.bucket_key.arn
  #   ]
  # }
  statement {
    sid    = "ListObjectsInBucket"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.private_files.arn,
      aws_s3_bucket.public_images.arn
    ]
  }
  statement {
    sid    = "AllObjectActions"
    effect = "Allow"
    actions = [
      "s3:*",
    ]
    resources = [
      "${aws_s3_bucket.private_files.arn}/*",
      "${aws_s3_bucket.public_images.arn}/*"
    ]
  }
}

resource "aws_iam_policy" "zhe_buckets" {
  name        = "zenhub${var.env}-buckets"
  path        = "/"
  description = "Policy to access zhe buckets"

  policy = data.aws_iam_policy_document.zhe_buckets.json
}

resource "aws_iam_group" "zhe_buckets" {
  name = "zenhub${var.env}-buckets"
}

resource "aws_iam_group_policy_attachment" "zhe_buckets" {
  group      = aws_iam_group.zhe_buckets.name
  policy_arn = aws_iam_policy.zhe_buckets.arn
}

resource "aws_iam_user" "zhe_buckets" {
  name = "zenhub${var.env}-buckets"

  tags = {
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_iam_user_group_membership" "zhe_buckets" {
  user = aws_iam_user.zhe_buckets.name

  groups = [
    aws_iam_group.zhe_buckets.name,
  ]
}
