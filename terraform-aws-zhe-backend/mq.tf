resource "random_password" "rabbitmq_pass" {
  count            = var.create_mq ? 1 : 0
  length           = 16
  special          = true
  override_special = "!-_"
}

resource "aws_mq_broker" "zhe_rabbitmq" {
  count                   = var.create_mq ? 1 : 0
  broker_name             = "zenhub${var.env}-toad-rabbitmq"
  engine_type             = "RabbitMQ"
  engine_version          = var.mq_engine_version
  host_instance_type      = var.mq_vars.instance_type
  security_groups         = [aws_security_group.zhe_vpc.id]
  deployment_mode         = var.mq_vars.deployment_mode
  authentication_strategy = "simple"
  publicly_accessible     = false
  subnet_ids              = [aws_subnet.zhe_db[0].id]
  storage_type            = "ebs"

  user {
    username = var.mq_user
    password = random_password.rabbitmq_pass[count.index].result
  }
}
