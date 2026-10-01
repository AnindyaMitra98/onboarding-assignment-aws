variable "queue_name" {
  description = "Name of the SQS queue. The dead-letter queue gets a \"-dlq\" suffix."
  type        = string
}

variable "sns_topic_arn" {
  description = "ARN of the SNS topic the queue subscribes to."
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "Visibility timeout; must be at least the consuming Lambda's timeout."
  type        = number
  default     = 180
}

variable "max_receive_count" {
  description = "Receives before a message is moved to the dead-letter queue."
  type        = number
  default     = 3
}
