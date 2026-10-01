# Root module: module callouts only. All resources live in ./modules.

locals {
  # NAME_PREFIX-onboarding-FIRST_INITIALLAST_NAME, e.g. aw1dd-onboarding-rkumar
  name = "${var.name_prefix}-onboarding-${var.owner}"
}

module "s3_bucket" {
  source = "./modules/s3_bucket"

  bucket_name   = "${local.name}-s3-bucket"
  force_destroy = true
}

module "sns_topic" {
  source = "./modules/sns_topic"

  topic_name = "${local.name}-sns-topic"
}

module "sqs_queue" {
  source = "./modules/sqs_queue"

  queue_name    = "${local.name}-sqs-queue"
  sns_topic_arn = module.sns_topic.topic_arn
}

module "read_lambda" {
  source = "./modules/lambda_function"

  function_name = "${local.name}-read-lambda"
  description   = "Reads CSV files from S3 and publishes each line as a JSON event to SNS"
  source_dir    = "${path.root}/../lambdas/read_lambda"
  timeout       = 60

  environment_variables = {
    BUCKET_NAME   = module.s3_bucket.bucket_name
    SNS_TOPIC_ARN = module.sns_topic.topic_arn
  }

  policy_statements = [
    {
      sid       = "ReadInputCsv"
      actions   = ["s3:GetObject"]
      resources = ["${module.s3_bucket.bucket_arn}/${var.input_prefix}*"]
    },
    {
      sid       = "PublishEvents"
      actions   = ["sns:Publish"]
      resources = [module.sns_topic.topic_arn]
    },
  ]
}

module "write_lambda" {
  source = "./modules/lambda_function"

  function_name = "${local.name}-write-lambda"
  description   = "Consumes JSON events from SQS and saves each one as a file in S3"
  source_dir    = "${path.root}/../lambdas/write_lambda"
  timeout       = 30

  environment_variables = {
    BUCKET_NAME   = module.s3_bucket.bucket_name
    OUTPUT_PREFIX = var.output_prefix
  }

  sqs_event_source = {
    queue_arn  = module.sqs_queue.queue_arn
    batch_size = 10
  }

  policy_statements = [
    {
      sid       = "WriteOutputJson"
      actions   = ["s3:PutObject"]
      resources = ["${module.s3_bucket.bucket_arn}/${var.output_prefix}*"]
    },
  ]
}

module "s3_notification" {
  source = "./modules/s3_notification"

  bucket_name   = module.s3_bucket.bucket_name
  bucket_arn    = module.s3_bucket.bucket_arn
  function_name = module.read_lambda.function_name
  function_arn  = module.read_lambda.function_arn
  filter_prefix = var.input_prefix
  filter_suffix = ".csv"
}
