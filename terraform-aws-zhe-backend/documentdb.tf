resource "random_password" "documentdb_pass" {
  count            = var.create_documentdb ? 1 : 0
  length           = 16
  special          = true
  override_special = "!-_"
}

resource "aws_docdb_cluster" "zhe" {
  count                           = var.create_documentdb ? 1 : 0
  cluster_identifier              = "zenhub${var.env}-mongo"
  engine                          = "docdb"
  engine_version                  = "${var.documentdb_engine_version}.0"
  master_username                 = var.documentdb_user
  master_password                 = random_password.documentdb_pass[count.index].result
  backup_retention_period         = 5
  skip_final_snapshot             = false
  final_snapshot_identifier       = "final${var.env}"
  storage_encrypted               = true
  port                            = var.documentdb_port
  db_subnet_group_name            = aws_docdb_subnet_group.zhe[count.index].name
  vpc_security_group_ids          = [aws_security_group.zhe_vpc.id]
  db_cluster_parameter_group_name = aws_docdb_cluster_parameter_group.zhe[count.index].name
  enabled_cloudwatch_logs_exports = ["audit", "profiler"]
  tags = {
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_docdb_cluster_instance" "cluster_instances" {
  count              = var.create_documentdb ? var.documentdb_vars.instance_count : 0
  identifier         = "zenhub${var.env}-mongo-${count.index}"
  cluster_identifier = aws_docdb_cluster.zhe[count.index].id
  instance_class     = var.documentdb_vars.instance_class
  engine             = "docdb"
  tags = {
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_docdb_subnet_group" "zhe" {
  count      = var.create_documentdb ? 1 : 0
  name       = "zenhub${var.env}-docdb-group"
  subnet_ids = aws_subnet.zhe_db[*].id
  tags = {
    Name        = "Zenhub ${var.env} docDB subnet group"
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_docdb_cluster_parameter_group" "zhe" {
  count       = var.create_documentdb ? 1 : 0
  family      = "docdb${var.documentdb_engine_version}"
  name        = "zenhub${var.env}-group"
  description = "docdb cluster parameter group for Zenhub"

  # FIX-ME
  parameter {
    name  = "tls"
    value = "disabled"
  }
  tags = {
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}
