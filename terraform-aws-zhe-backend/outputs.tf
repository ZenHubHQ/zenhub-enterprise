# Databases
output "zhe_postgresql_endpoint" {
  description = "PostgreSQL connection endpoint"
  sensitive   = true
  value       = var.create_postgresql ? "postgresql://${var.postgres_user}:${random_password.postgresql_pass[0].result}@${aws_db_instance.zhe_postgresql[0].endpoint}/${aws_db_instance.zhe_postgresql[0].name}?sslmode=disable" : null
}

output "zhe_mongo_endpoint" {
  description = "mongo connection endpoint"
  sensitive   = true
  value       = var.create_documentdb ? "mongodb://${var.documentdb_user}:${random_password.documentdb_pass[0].result}@${aws_docdb_cluster.zhe[0].endpoint}:${var.documentdb_port}/${var.documentdb_dbname}?replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false" : null
}

# Cache
output "zhe_redis_endpoint" {
  description = "redis connection endpoint"
  sensitive   = true
  value       = var.create_redis ? "redis://${aws_elasticache_cluster.zhe_redis[0].cache_nodes.0.address}:${aws_elasticache_cluster.zhe_redis[0].cache_nodes.0.port}/0" : null
}

# Buckets
output "zhe_bucket_images_name" {
  description = "images bucket name"
  value       = aws_s3_bucket.public_images.id
}

output "zhe_bucket_images_region" {
  description = "bucket images region"
  value       = aws_s3_bucket.public_images.region
}

output "zhe_bucket_images_domain_name" {
  description = "bucket images domain name"
  value       = aws_s3_bucket.public_images.bucket_regional_domain_name
}

output "zhe_bucket_files_name" {
  description = "files bucket name"
  value       = aws_s3_bucket.private_files.id
}

output "zhe_bucket_files_region" {
  description = "files bucket region"
  value       = aws_s3_bucket.private_files.region
}

output "zhe_bucket_files_domain_name" {
  description = "files bucket domain name"
  value       = aws_s3_bucket.private_files.bucket_regional_domain_name
}

output "zhe_bucket_iam_user" {
  description = "IAM user with access to buckets"
  value       = aws_iam_user.zhe_buckets.name
}

output "zhe_subnets_id" {
  description = "The ID of the ZHE Subnet"
  value       = aws_subnet.zhe_db.*.id
}

output "zhe_sg_id" {
  description = "The ID of the ZHE SG"
  value       = aws_security_group.zhe_vpc.id
}
