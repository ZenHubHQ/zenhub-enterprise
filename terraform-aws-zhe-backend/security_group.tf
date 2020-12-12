resource "aws_security_group" "zhe_vpc" {
  name   = "zhe_allow_vpc"
  vpc_id = var.vpc_id

  tags = {
    Name        = "zenhub${var.env}-backend"
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }

  # ingress {
  #   description = "All from VPC"
  #   cidr_blocks = [data.aws_vpc.zhe.cidr_block]
  #   protocol    = "-1"
  #   self        = true
  #   from_port   = 0
  #   to_port     = 0
  # }

  # egress {
  #   from_port   = 0
  #   to_port     = 0
  #   protocol    = "-1"
  #   cidr_blocks = ["0.0.0.0/0"]
  # }
}

resource "aws_security_group_rule" "zhe_db_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 65535
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.zhe_vpc.id
  # cidr_blocks       = [data.aws_vpc.zhe.cidr_block]
}

resource "aws_security_group_rule" "zhe_ingress_docuemntdb" {
  count             = var.create_documentdb ? 1 : 0
  type              = "ingress"
  from_port         = var.documentdb_port
  to_port           = var.documentdb_port
  protocol          = "tcp"
  cidr_blocks       = [data.aws_vpc.zhe.cidr_block]
  security_group_id = aws_security_group.zhe_vpc.id
}

resource "aws_security_group_rule" "zhe_ingress_redis" {
  count             = var.create_redis ? 1 : 0
  type              = "ingress"
  from_port         = var.redis_port
  to_port           = var.redis_port
  protocol          = "tcp"
  cidr_blocks       = [data.aws_vpc.zhe.cidr_block]
  security_group_id = aws_security_group.zhe_vpc.id
}

resource "aws_security_group_rule" "zhe_ingress_postgres" {
  count             = var.create_postgresql ? 1 : 0
  type              = "ingress"
  from_port         = var.postgres_port
  to_port           = var.postgres_port
  protocol          = "tcp"
  cidr_blocks       = [data.aws_vpc.zhe.cidr_block]
  security_group_id = aws_security_group.zhe_vpc.id
}

resource "aws_security_group_rule" "zhe_ingress_mq" {
  count             = var.create_mq ? 1 : 0
  type              = "ingress"
  from_port         = var.mq_port
  to_port           = var.mq_port
  protocol          = "tcp"
  cidr_blocks       = [data.aws_vpc.zhe.cidr_block]
  security_group_id = aws_security_group.zhe_vpc.id
}

# Network ACL

resource "aws_network_acl" "zhe" {
  vpc_id     = var.vpc_id
  subnet_ids = aws_subnet.zhe_db[*].id
  tags = {
    Name        = "zenhub${var.env}-backend"
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_network_acl_rule" "zhe_db_egress" {
  network_acl_id = aws_network_acl.zhe.id
  rule_number    = 100
  egress         = true
  protocol       = -1
  rule_action    = "allow"
  cidr_block     = "0.0.0.0/0"
  # cidr_block     = data.aws_vpc.zhe.cidr_block
}

resource "aws_network_acl_rule" "zhe_ingress_docuemntdb" {
  count          = var.create_documentdb ? 1 : 0
  network_acl_id = aws_network_acl.zhe.id
  rule_number    = 100
  egress         = false
  protocol       = "tcp"
  rule_action    = "allow"
  cidr_block     = data.aws_vpc.zhe.cidr_block
  from_port      = var.documentdb_port
  to_port        = var.documentdb_port
}

resource "aws_network_acl_rule" "zhe_ingress_redis" {
  count          = var.create_redis ? 1 : 0
  network_acl_id = aws_network_acl.zhe.id
  rule_number    = 200
  egress         = false
  protocol       = "tcp"
  rule_action    = "allow"
  cidr_block     = data.aws_vpc.zhe.cidr_block
  from_port      = var.redis_port
  to_port        = var.redis_port
}

resource "aws_network_acl_rule" "zhe_ingress_postgres" {
  count          = var.create_postgresql ? 1 : 0
  network_acl_id = aws_network_acl.zhe.id
  rule_number    = 300
  egress         = false
  protocol       = "tcp"
  rule_action    = "allow"
  cidr_block     = data.aws_vpc.zhe.cidr_block
  from_port      = var.postgres_port
  to_port        = var.postgres_port
}

resource "aws_network_acl_rule" "zhe_ingress_mq" {
  count          = var.create_mq ? 1 : 0
  network_acl_id = aws_network_acl.zhe.id
  rule_number    = 400
  egress         = false
  protocol       = "tcp"
  rule_action    = "allow"
  cidr_block     = data.aws_vpc.zhe.cidr_block
  from_port      = var.mq_port
  to_port        = var.mq_port
}
