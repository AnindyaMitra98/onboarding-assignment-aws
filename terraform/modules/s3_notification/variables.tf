variable "bucket_name" {
  description = "Bucket that emits the notifications."
  type        = string
}

variable "bucket_arn" {
  description = "ARN of the bucket, used to scope the Lambda invoke permission."
  type        = string
}

variable "function_name" {
  description = "Name of the Lambda function to invoke."
  type        = string
}

variable "function_arn" {
  description = "ARN of the Lambda function to invoke."
  type        = string
}

variable "filter_prefix" {
  description = "Only objects under this key prefix trigger the function."
  type        = string
  default     = null
}

variable "filter_suffix" {
  description = "Only objects with this key suffix trigger the function."
  type        = string
  default     = null
}
