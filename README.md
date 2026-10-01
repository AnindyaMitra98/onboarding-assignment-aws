# Onboarding Assignment – AWS

Project 1 (standalone): a CSV file uploaded to S3 is split into one JSON event per line,
fanned out through SNS → SQS, and each event is written back to the same bucket as its own file.

```
S3 (input/*.csv) ──► read-lambda ──► SNS ──► SQS ──► write-lambda ──► S3 (output/<file>/<line>.json)
                                              │
                                              └─► DLQ (after 3 failed receives)
```

## Tool versions

| Tool | Version | Notes |
|------|---------|-------|
| Terraform | 0.13.7 | pinned in `versions.tf` and `terragrunt.hcl` |
| Terragrunt | 0.29.2 | pinned in `terragrunt.hcl` |
| AWS provider | ~> 5.0 | supports Terraform 0.13 (v6 needs Terraform 1.x) |
| Archive provider | ~> 2.2.0 | |
| Python (Lambda runtime) | 3.9 | `python3.9`; code avoids 3.10+ syntax |

Terraform 0.13 has no `.terraform.lock.hcl`, so provider versions are held by the constraints above.

## Layout

```
lambdas/
  read_lambda/handler.py     # S3 trigger → parse CSV → PublishBatch to SNS
  write_lambda/handler.py    # SQS trigger → PutObject per event (partial batch failures)
  tests/                     # pytest unit tests (boto3 mocked)
terraform/
  terragrunt.hcl             # version pins, local backend (generates backend.tf), inputs
  main.tf                    # root module: module callouts only
  variables.tf
  modules/
    s3_bucket/               # bucket, public-access block, SSE
    sns_topic/
    sqs_queue/               # queue, DLQ, queue policy, SNS subscription
    lambda_function/         # shared by both Lambdas: zip, role, policy, log group, optional SQS trigger
    s3_notification/         # S3 → Lambda invoke permission + bucket notification
  state/terraform.tfstate    # Terraform state, committed to the repo
sample-data/people.csv
```

## Conventions

- **Naming:** every resource is named `NAME_PREFIX-onboarding-FIRST_INITIALLAST_NAME-<resource>`,
  e.g. `aw1dd-onboarding-rkumar-s3-bucket`. Set `name_prefix` and `owner` in the `inputs` block of `terraform/terragrunt.hcl`.
- **Tags:** `Project = Onboarding` is applied to all resources through the provider's `default_tags`.
- **Configuration:** the bucket name, SNS topic ARN and output prefix reach the Lambdas through environment variables.
- **No trigger loop:** read-lambda only fires for `input/*.csv`; write-lambda only writes under `output/`.
- **Idempotent output:** each event's key comes from its source file and line number, so a retried message overwrites its own file instead of creating a duplicate.

## Deploy

```sh
cd terraform
terragrunt init
terragrunt plan
terragrunt apply
```

Terragrunt generates `backend.tf` with a `local` backend pointing at `state/terraform.tfstate`.
After `apply`, commit `terraform/state/terraform.tfstate` so the state stays in the repository.

## Try it

```sh
BUCKET=$(terraform -chdir=terraform output -raw bucket_name)
aws s3 cp sample-data/people.csv s3://$BUCKET/input/people.csv
aws s3 ls s3://$BUCKET/output/people/
#   000002.json  000003.json  000004.json   (CSV line numbers; line 1 is the header)
aws s3 cp s3://$BUCKET/output/people/000002.json -
```

Logs are in CloudWatch under `/aws/lambda/<name>-read-lambda` and `/aws/lambda/<name>-write-lambda`.

## Tests

```sh
pip install pytest            # Python 3.9, matching the Lambda runtime
python -m pytest lambdas/tests
```
