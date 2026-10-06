# Terraform state is stored in the repository, as the assignment requires.
terraform {
  backend "local" {
    path = "state/terraform.tfstate"
  }
}
