# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Onboarding assignment: a CSV uploaded to S3 is split into one JSON event per line and written back to the same bucket.

```
S3 input/*.csv → read-lambda → SNS → SQS (+DLQ) → write-lambda → S3 output/<csv-name>/<line:06d>.json
```

Assignment rules that constrain any change:
- Root module (`terraform/main.tf`) contains **only module callouts** (plus the `local.name` naming local). Every resource lives in `terraform/modules/*`.
- Both Lambdas use the **one shared** `modules/lambda_function` module.
- Names: `<name_prefix>-onboarding-<owner>-<resource>` → `aw1dd-onboarding-amitra-*`. `name_prefix`/`owner` are set in the `inputs` block of `terraform/terragrunt.hcl`.
- Every resource is tagged `Project = Onboarding` — done once via provider `default_tags` in `providers.tf`, not per resource.
- Terraform state is committed to the repo (`terraform/state/terraform.tfstate`). Commit it after every apply.
- Work on a branch off `master`; deliver via PR.

## Pinned versions (required by the assignment)

- **Terraform 0.13.7**, **Terragrunt 0.29.2** — both enforced in `terragrunt.hcl`; `versions.tf` also pins Terraform.
- **Python 3.9** Lambda runtime (default in `modules/lambda_function/variables.tf`); code must stay 3.9-compatible (no `match`, no `X | Y` types, etc.).
- AWS provider `~> 5.0` (v5 still supports TF 0.13; v6 needs TF 1.x). Archive provider `~> 2.2.0`.

The system `terraform` on this machine is 1.x, so put a 0.13.7 `terraform` binary and `terragrunt` 0.29.2 first on `PATH` before running Terragrunt, or the version constraint will fail.

Terraform 0.13 gotchas already hit in this repo:
- No `optional()` in object types — callers must pass every attribute (e.g. `sqs_event_source = { queue_arn, batch_size }`).
- Avoid `cond ? [] : [ {...} ]` (inconsistent tuple types); use a `count`-ed resource instead (see `aws_iam_role_policy.sqs`).
- Validation `error_message` must start with a capital letter and end with `.`.
- No `.terraform.lock.hcl`, no `-chdir`, no `output -raw` (plain `terragrunt output <name>` prints strings unquoted).
- `plan -refresh=false` defers `archive_file` data sources; run a normal plan to see real `source_code_hash`.

## Commands

All Terraform commands run from `terraform/` via Terragrunt (it generates the git-ignored `backend.tf` with a local backend at `state/terraform.tfstate`):

```sh
cd terraform
terraform fmt -recursive -check
terragrunt init
terragrunt validate
terragrunt plan -out=x.tfplan     # review, then:
terragrunt apply x.tfplan         # apply the reviewed plan, not -auto-approve
```

Lambda unit tests (boto3 is stubbed in `lambdas/tests/conftest.py`, so only pytest is needed):

```sh
python -m pytest lambdas/tests
python -m pytest lambdas/tests/test_read_lambda.py::test_publishes_in_batches_of_ten
uv run --no-project --python 3.9 --with pytest python -m pytest lambdas/tests   # on the real runtime version
```

End-to-end check against the deployed stack:

```sh
aws s3 cp sample-data/sample.csv s3://aw1dd-onboarding-amitra-s3-bucket/input/sample.csv
aws s3 ls s3://aw1dd-onboarding-amitra-s3-bucket/output/sample/
```

In Git Bash, set `MSYS_NO_PATHCONV=1` before `aws logs ... --log-group-name /aws/lambda/...`, otherwise the path is rewritten to a Windows path.

## Architecture notes (cross-file contracts)

- **read-lambda → write-lambda contract:** read-lambda sends each row as the SNS message body (JSON) plus message attributes `source_key` and `line_number`. The SNS→SQS subscription uses `raw_message_delivery = true`, so the SQS body is the bare JSON and the SNS attributes arrive as SQS `messageAttributes`. write-lambda builds the output key from those attributes (falls back to `messageId`). Changing any of these three pieces breaks the others.
- **No trigger loop:** the S3 notification fires only for `input/` + `.csv`; write-lambda writes only under `OUTPUT_PREFIX` (`output/`). The read/write IAM policies are scoped to those same prefixes (`var.input_prefix` / `var.output_prefix` in the root).
- **Retries are idempotent:** output keys are deterministic per source file + line, so redelivered messages overwrite rather than duplicate.
- **Failure handling:** read-lambda uses `sns.publish_batch` (10 per call) and raises on any failed entry so S3's async retry reprocesses the file. write-lambda returns `batchItemFailures` (event source mapping has `ReportBatchItemFailures`); messages failing 3 receives go to the `-dlq` queue.
- **Shared lambda module:** zips `source_dir` with `archive_file` into `terraform/build/` (git-ignored), always grants log-write to its own log group, adds extra permissions from `policy_statements`, and — only when `sqs_event_source` is set — creates the SQS consume policy and event source mapping. S3→Lambda invoke permission and bucket notification live in the separate `s3_notification` module.
- SQS visibility timeout (180s) must stay ≥ write-lambda timeout.
- `conftest.py` sets `sys.dont_write_bytecode` so `__pycache__` isn't zipped into the Lambda packages.
