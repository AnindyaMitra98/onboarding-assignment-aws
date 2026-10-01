terraform_version_constraint  = "= 0.13.7"
terragrunt_version_constraint = "= 0.29.2"

# Terraform state is stored in the repository, as the assignment requires.
remote_state {
  backend = "local"

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }

  config = {
    path = "state/terraform.tfstate"
  }
}

inputs = {
  # Replace with the NAME_PREFIX from the provided variables file.
  name_prefix = "aw1dd"

  # First initial + last name, lowercase (e.g. Rahul Kumar -> "rkumar").
  owner = "pmitra"

  aws_region = "us-east-1"
}
