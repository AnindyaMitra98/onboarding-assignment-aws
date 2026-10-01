variable "name_prefix" {
  description = "NAME_PREFIX for all resource names, e.g. \"aw1dd\"."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.name_prefix))
    error_message = "name_prefix must be lowercase letters, digits or hyphens (it is used in the S3 bucket name)."
  }
}

variable "owner" {
  description = "First initial + last name, lowercase, e.g. Rahul Kumar -> \"rkumar\"."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]+$", var.owner))
    error_message = "owner must be lowercase letters or digits only."
  }
}

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "input_prefix" {
  description = "Key prefix where CSV files are uploaded; uploads here trigger read-lambda."
  type        = string
  default     = "input/"
}

variable "output_prefix" {
  description = "Key prefix where write-lambda stores the JSON files. Must differ from input_prefix."
  type        = string
  default     = "output/"
}
