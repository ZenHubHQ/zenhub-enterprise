resource "random_password" "redis_auth_token" {
  count = var.create_redis ? 1 : 0
  # ElastiCache auth tokens may not contain "/", "\"" or "@"; alphanumeric also keeps the URL output unescaped.
  length  = 64
  special = false
}

resource "aws_elasticache_replication_group" "zhe_redis" {
  count                         = var.create_redis ? 1 : 0
  replication_group_id          = "zenhub${var.env}-cache"
  replication_group_description = "ZenHub Enterprise Redis"
  engine                        = "redis"
  node_type                     = var.redis_vars.node_type
  number_cache_clusters         = 1
  parameter_group_name          = aws_elasticache_parameter_group.zhe_redis[count.index].name
  engine_version                = "${var.redis_engine_version}.6"
  port                          = var.redis_port
  subnet_group_name             = aws_elasticache_subnet_group.zhe[count.index].name
  security_group_ids            = [aws_security_group.zhe_vpc.id]
  at_rest_encryption_enabled    = true
  transit_encryption_enabled    = true
  auth_token                    = random_password.redis_auth_token[count.index].result
  tags = {
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_elasticache_parameter_group" "zhe_redis" {
  count  = var.create_redis ? 1 : 0
  name   = "ZenHub${var.env}"
  family = "redis${var.redis_engine_version}"

  parameter {
    name  = "maxmemory-policy"
    value = "noeviction"
  }
}

resource "aws_elasticache_subnet_group" "zhe" {
  count      = var.create_redis ? 1 : 0
  name       = "zenhub${var.env}-cache-group"
  subnet_ids = aws_subnet.zhe_db[*].id
}
