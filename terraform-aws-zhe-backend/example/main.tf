module "zhe" {
  source = "../../modules/zhe_data"

  env    = "-test"
  region = "us-west-2"
  vpc_id = "vpc-0000aaaa11b2cc111"

  postgres_vars = {
    instance_class = "db.t3.small"
  }

  redis_vars = {
    node_type = "cache.t3.small"
  }

  documentdb_vars = {
    instance_class = "db.t3.medium"
    instance_count = "1"
  }

  mq_vars = {
    instance_type   = "mq.t3.micro"
    deployment_mode = "SINGLE_INSTANCE"
  }

  create_postgresql = true
  create_redis      = true
  create_documentdb = true
  create_mq         = true

}
