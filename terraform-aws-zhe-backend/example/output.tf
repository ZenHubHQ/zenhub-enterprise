output "sensitive_information" {
  sensitive = true
  value = map(
    "postgres:", module.zhe.zhe_postgresql_endpoint,
    "redis:", module.zhe.zhe_redis_endpoint,
    "mongo:", module.zhe.zhe_mongo_endpoint
  )
}

output "zhe_bucket_images_domain_name" {
  description = "bucket images domain name"
  value       = module.zhe.zhe_bucket_images_domain_name
}

output "zhe_bucket_images_name" {
  description = "images bucket name"
  value       = module.zhe.zhe_bucket_images_name
}

output "zhe_bucket_images_region" {
  description = "bucket images region"
  value       = module.zhe.zhe_bucket_images_region
}

output "zhe_bucket_files_name" {
  description = "files bucket name"
  value       = module.zhe.zhe_bucket_files_name
}

output "zhe_bucket_files_region" {
  description = "bucket documents region"
  value       = module.zhe.zhe_bucket_files_region
}

output "zhe_bucket_iam_user" {
  description = "IAM user with access to buckets"
  value       = module.zhe.zhe_bucket_iam_user
}
