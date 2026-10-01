data "archive_file" "this" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.root}/build/${var.function_name}.zip"
}

resource "aws_iam_role" "this" {
  name = "${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

locals {
  logging_statement = {
    Sid      = "WriteLogs"
    Effect   = "Allow"
    Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    Resource = ["${aws_cloudwatch_log_group.this.arn}:*"]
  }

  # Permissions the Lambda service needs to poll the queue on the function's behalf.
  sqs_statements = var.sqs_event_source == null ? [] : [{
    Sid      = "ConsumeQueue"
    Effect   = "Allow"
    Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    Resource = [var.sqs_event_source.queue_arn]
  }]

  extra_statements = [for s in var.policy_statements : {
    Sid      = s.sid
    Effect   = "Allow"
    Action   = s.actions
    Resource = s.resources
  }]
}

resource "aws_iam_role_policy" "this" {
  name = "${var.function_name}-policy"
  role = aws_iam_role.this.id

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = concat([local.logging_statement], local.sqs_statements, local.extra_statements)
  })
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "this" {
  function_name    = var.function_name
  description      = var.description
  role             = aws_iam_role.this.arn
  runtime          = var.runtime
  handler          = var.handler
  filename         = data.archive_file.this.output_path
  source_code_hash = data.archive_file.this.output_base64sha256
  timeout          = var.timeout
  memory_size      = var.memory_size

  environment {
    variables = var.environment_variables
  }

  depends_on = [aws_cloudwatch_log_group.this, aws_iam_role_policy.this]
}

resource "aws_lambda_event_source_mapping" "sqs" {
  count = var.sqs_event_source == null ? 0 : 1

  event_source_arn        = var.sqs_event_source.queue_arn
  function_name           = aws_lambda_function.this.arn
  batch_size              = var.sqs_event_source.batch_size
  function_response_types = ["ReportBatchItemFailures"]

  depends_on = [aws_iam_role_policy.this]
}
