resource "aws_elasticache_cluster" "zhe_redis" {
  count                = var.create_redis ? 1 : 0
  cluster_id           = "zenhub${var.env}-cache"
  engine               = "redis"
  node_type            = var.redis_vars.node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis${var.redis_engine_version}"
  engine_version       = "${var.redis_engine_version}.6"
  port                 = var.redis_port
  subnet_group_name    = aws_elasticache_subnet_group.zhe[count.index].name
  security_group_ids   = [aws_security_group.zhe_vpc.id]
  tags = {
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_elasticache_subnet_group" "zhe" {
  count      = var.create_redis ? 1 : 0
  name       = "zenhub${var.env}-cache-group"
  subnet_ids = aws_subnet.zhe_db[*].id
}
