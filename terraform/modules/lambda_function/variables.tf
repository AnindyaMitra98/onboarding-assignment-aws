variable "function_name" {
  description = "Name of the Lambda function; also used for its role, policy and log group."
  type        = string
}

variable "description" {
  description = "Description of the Lambda function."
  type        = string
  default     = ""
}

variable "source_dir" {
  description = "Directory containing the function's Python source, zipped on apply."
  type        = string
}

variable "handler" {
  description = "Function entrypoint in module.function form."
  type        = string
  default     = "handler.lambda_handler"
}

variable "runtime" {
  description = "Lambda runtime."
  type        = string
  default     = "python3.12"
}

variable "timeout" {
  description = "Function timeout in seconds."
  type        = number
  default     = 30
}

variable "memory_size" {
  description = "Memory in MB."
  type        = number
  default     = 128
}

variable "environment_variables" {
  description = "Environment variables passed to the function."
  type        = map(string)
  default     = {}
}

variable "policy_statements" {
  description = "Additional IAM Allow statements for the function's role."
  type = list(object({
    sid       = string
    actions   = list(string)
    resources = list(string)
  }))
  default = []
}

variable "sqs_event_source" {
  description = "Optional SQS queue that triggers the function. Grants the needed SQS permissions automatically."
  type = object({
    queue_arn  = string
    batch_size = optional(number, 10)
  })
  default = null
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 14
}
