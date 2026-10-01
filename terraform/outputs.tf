output "bucket_name" {
  description = "Bucket for input CSVs and output JSON files."
  value       = module.s3_bucket.bucket_name
}

output "sns_topic_arn" {
  description = "Topic read-lambda publishes to."
  value       = module.sns_topic.topic_arn
}

output "sqs_queue_url" {
  description = "Queue write-lambda consumes from."
  value       = module.sqs_queue.queue_url
}

output "sqs_dlq_arn" {
  description = "Dead-letter queue for events write-lambda could not save."
  value       = module.sqs_queue.dlq_arn
}

output "read_lambda_name" {
  description = "Name of read-lambda."
  value       = module.read_lambda.function_name
}

output "write_lambda_name" {
  description = "Name of write-lambda."
  value       = module.write_lambda.function_name
}
