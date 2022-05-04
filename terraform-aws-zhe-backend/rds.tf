resource "random_password" "postgresql_pass" {
  count            = var.create_postgresql ? 1 : 0
  length           = 16
  special          = true
  override_special = "!-_"
}

resource "aws_db_instance" "zhe_postgresql" {
  count                     = var.create_postgresql ? 1 : 0
  allocated_storage         = 20
  storage_type              = "gp2"
  port                      = var.postgres_port
  engine                    = "postgres"
  engine_version            = var.postgres_engine_version
  instance_class            = var.postgres_vars.instance_class
  identifier                = "zenhub${var.env}-raptor"
  name                      = var.postgres_dbname
  username                  = var.postgres_user
  password                  = random_password.postgresql_pass[count.index].result
  storage_encrypted         = true
  multi_az                  = false
  db_subnet_group_name      = aws_db_subnet_group.zhe[count.index].name
  copy_tags_to_snapshot     = true
  vpc_security_group_ids    = [aws_security_group.zhe_vpc.id]
  skip_final_snapshot       = false
  final_snapshot_identifier = "final${var.env}"
  tags = {
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_db_subnet_group" "zhe" {
  count      = var.create_postgresql ? 1 : 0
  name       = "zenhub${var.env}-db-group"
  subnet_ids = aws_subnet.zhe_db[*].id

  tags = {
    Name        = "zenhub${var.env}-db-group"
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}
