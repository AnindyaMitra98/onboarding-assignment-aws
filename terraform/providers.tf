provider "aws" {
  region = var.aws_region

  # Applied to every taggable resource created by every module.
  default_tags {
    tags = {
      Project = "Onboarding"
    }
  }
}
