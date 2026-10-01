variable "bucket_name" {
  description = "Globally unique name of the bucket."
  type        = string
}

variable "force_destroy" {
  description = "Allow Terraform to delete the bucket even when it still contains objects."
  type        = bool
  default     = false
}
