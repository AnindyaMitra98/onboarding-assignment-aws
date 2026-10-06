# Project Guide: CSV → JSON Pipeline on AWS

A plain-English walkthrough of every piece of code in this repository. It is written for someone new to DevOps, so you can understand the project yourself and explain it to your teammates.

**Contents**

1. [What the project does](#1-what-the-project-does)
2. [Concepts you need first](#2-concepts-you-need-first)
3. [What is in the repository](#3-what-is-in-the-repository)
4. [Following one CSV file through the system](#4-following-one-csv-file-through-the-system)
5. [The Terraform code, file by file](#5-the-terraform-code-file-by-file)
6. [How values travel through Terraform](#6-how-values-travel-through-terraform)
7. [The Python code, line by line](#7-the-python-code-line-by-line)
8. [The tests](#8-the-tests)
9. [Design decisions and why we made them](#9-design-decisions-and-why-we-made-them)
10. [How to run everything](#10-how-to-run-everything)
11. [Questions teammates are likely to ask](#11-questions-teammates-are-likely-to-ask)

---

## 1. What the project does

You upload a CSV file (a spreadsheet saved as text) to an S3 bucket. The system automatically turns **each line** of that CSV into a separate **JSON file** and saves those files back into the same bucket.

```
                 ┌────────────┐     ┌──────────┐     ┌──────────┐     ┌─────────────┐
 upload CSV ───► │ read-lambda│ ──► │   SNS    │ ──► │   SQS    │ ──► │ write-lambda│ ───► one JSON file
 to S3 input/    │  (Python)  │     │  topic   │     │  queue   │     │  (Python)   │      per CSV line
                 └────────────┘     └──────────┘     └────┬─────┘     └─────────────┘      in S3 output/
                                                          │ fails 3 times
                                                          ▼
                                                    ┌──────────┐
                                                    │   DLQ    │  (dead-letter queue: holds broken messages)
                                                    └──────────┘
```

Example: upload `sample.csv`:

```csv
order_id,customer,product,quantity,price,city
1001,Rahul Kumar,Laptop,1,55000.00,Bengaluru
1002,Priya Sharma,Headphones,2,1999.50,Pune
```

A few seconds later the bucket contains:

```
output/sample/000002.json   →  {"order_id": "1001", "customer": "Rahul Kumar", "product": "Laptop", ...}
output/sample/000003.json   →  {"order_id": "1002", "customer": "Priya Sharma", "product": "Headphones", ...}
```

The file name is the **line number in the CSV** (line 1 is the header row, so the first data row is `000002`).

---

## 2. Concepts you need first

### AWS services used

| Service | What it is | Its job in this project |
|---|---|---|
| **S3** (Simple Storage Service) | Cloud storage for files (called *objects*), kept in *buckets*. Files are addressed by a *key*, like a path: `input/sample.csv`. | Holds the uploaded CSV and the generated JSON files. |
| **Lambda** | Runs your code without you managing a server. AWS starts it when an *event* happens, and you pay only while it runs. | Two Lambdas: one reads the CSV, one writes the JSON files. |
| **SNS** (Simple Notification Service) | A *publish/subscribe* service. You publish a message to a *topic*, and SNS pushes a copy to every *subscriber*. | read-lambda publishes one message per CSV line to the topic. |
| **SQS** (Simple Queue Service) | A *queue*: messages wait in it until a consumer picks them up and deletes them. | Buffers the messages between SNS and write-lambda, and retries if writing fails. |
| **DLQ** (Dead-Letter Queue) | A normal SQS queue used as a "lost and found" for messages that keep failing. | After 3 failed attempts, a message moves here instead of retrying forever. |
| **IAM** (Identity and Access Management) | AWS permissions. A *role* is an identity a service can use; a *policy* is a list of what that role may do. | Each Lambda gets its own role with only the permissions it needs. |
| **CloudWatch Logs** | Where AWS stores logs. Each Lambda writes to a *log group*. | Our Python `logger.info(...)` lines show up here. |
| **ARN** (Amazon Resource Name) | The unique ID of anything in AWS, e.g. `arn:aws:sns:us-east-1:123456789012:my-topic`. | Used to connect resources (e.g. "this queue subscribes to *that* topic ARN"). |

**Why SNS *and* SQS?** SNS pushes messages instantly but does not store or retry them for long. SQS stores messages until they are processed successfully. Combining them (the "fan-out" pattern) means more subscribers can be added to the topic later, while the queue makes sure nothing is lost.

### Tools used

| Tool | What it is |
|---|---|
| **Terraform** (v0.13.7) | *Infrastructure as Code*: you describe the AWS resources you want in `.tf` files, and Terraform creates, updates or deletes them to match. |
| **Python** (3.9) | The language both Lambdas are written in. |
| **boto3** | The AWS library for Python. Lambda includes it automatically, so we do not package it. |
| **pytest** | The Python testing tool used for the unit tests. |

### Terraform vocabulary

| Term | Meaning |
|---|---|
| **resource** | One thing to create in AWS, e.g. `resource "aws_s3_bucket" "this" { ... }`. |
| **data source** | Something Terraform *reads or computes* instead of creating, e.g. `data "archive_file"` builds a zip. |
| **variable** | An input to a module (like a function parameter). Used as `var.name`. |
| **local** | A named value computed inside a module (like a local variable). Used as `local.name`. |
| **output** | A value a module returns to whoever called it. Used as `module.<name>.<output>`. |
| **module** | A folder of `.tf` files that groups related resources. The folder you run Terraform in is the *root module*; it calls *child modules*. |
| **provider** | The plugin that talks to a platform. The `aws` provider turns `.tf` code into AWS API calls. |
| **state** | Terraform's record of what it created (`terraform.tfstate`). Terraform compares your code to the state to decide what to change. |
| **backend** | Where the state file is stored. We use the `local` backend: a file inside this repository. |
| **plan / apply / destroy** | *plan* shows what would change, *apply* makes the changes, *destroy* deletes everything. |

---

## 3. What is in the repository

```
.
├── PROJECT_GUIDE.md              ← this document
├── README.md                     ← short overview and commands
├── CLAUDE.md                     ← notes for the Claude Code AI assistant
├── .gitignore / .gitattributes   ← files git should ignore / line-ending rules
├── .python-version               ← tells Python tools to use 3.9
│
├── lambdas/                      ← the Python code
│   ├── read_lambda/handler.py    ← CSV → SNS
│   ├── write_lambda/handler.py   ← SQS → S3 JSON file
│   └── tests/                    ← unit tests for both
│
├── sample-data/                  ← example CSV files for testing
│   ├── sample.csv
│   └── people.csv
│
└── terraform/                    ← the infrastructure code
    ├── terraform.tfvars          ← variable values (name prefix, owner, region)
    ├── backend.tf                ← where state is stored
    ├── versions.tf               ← required Terraform and provider versions
    ├── providers.tf              ← AWS region + the Project=Onboarding tag
    ├── variables.tf              ← inputs the root module accepts
    ├── main.tf                   ← calls every module (no resources directly)
    ├── outputs.tf                ← values printed after apply
    ├── state/terraform.tfstate   ← Terraform state, committed to git
    └── modules/
        ├── s3_bucket/            ← the bucket
        ├── sns_topic/            ← the topic
        ├── sqs_queue/            ← queue, dead-letter queue, permissions, subscription
        ├── lambda_function/      ← used by BOTH Lambdas
        └── s3_notification/      ← "when a CSV lands in S3, run read-lambda"
```

Every module folder has the same three files, which is a Terraform convention:

- `main.tf`: the resources
- `variables.tf`: the inputs
- `outputs.tf`: the values it hands back (`s3_notification` has none because nothing needs its outputs)

---

## 4. Following one CSV file through the system

Here is exactly what happens, step by step, when you upload `sample.csv`:

1. **Upload.** You run `aws s3 cp sample-data/sample.csv s3://<bucket>/input/sample.csv`.
2. **S3 fires an event.** The bucket has a notification rule: *"when an object is created whose key starts with `input/` and ends with `.csv`, invoke read-lambda."* S3 calls read-lambda and passes it the bucket name and the file key.
3. **read-lambda runs** (`lambdas/read_lambda/handler.py`):
   - downloads `input/sample.csv` from S3,
   - reads it line by line, turning each line into a Python dictionary using the header row as keys,
   - converts each dictionary to JSON text,
   - publishes the JSON to the SNS topic, attaching two labels (*message attributes*): `source_key = input/sample.csv` and `line_number = 2, 3, ...`.
4. **SNS delivers to SQS.** The queue is subscribed to the topic, so every message lands in the queue.
5. **SQS triggers write-lambda.** AWS polls the queue and calls write-lambda with up to 10 messages at a time.
6. **write-lambda runs** (`lambdas/write_lambda/handler.py`), for each message:
   - checks that the body is valid JSON,
   - builds a file name from the labels: `sample` + line `2` → `output/sample/000002.json`,
   - saves the JSON to S3.
7. **Cleanup or retry.** Messages that were saved are deleted from the queue. A message that failed goes back on the queue and is retried. After 3 failures it moves to the dead-letter queue.

Both Lambdas log each step to CloudWatch, so you can follow the whole journey in the logs.

---

## 5. The Terraform code, file by file

### 5.1 `terraform/terraform.tfvars` and `terraform/backend.tf`: the control panel

`terraform.tfvars` is the file you edit to change settings:

```hcl
name_prefix = "aw1dd"
owner       = "amitra"
aws_region  = "us-east-1"
```
These are the **values** of the variables declared in `variables.tf`. Terraform loads a file named exactly `terraform.tfvars` automatically on every `plan` / `apply`, so no extra flags are needed. See [section 6](#6-how-values-travel-through-terraform).

`backend.tf` says where the state is stored:

```hcl
terraform {
  backend "local" {
    path = "state/terraform.tfstate"
  }
}
```
The assignment requires the state to live in the repository, so after every `apply` the state file is committed to git.

### 5.2 `terraform/versions.tf`: required versions

```hcl
required_version = "= 0.13.7"
aws     = { source = "hashicorp/aws",     version = "~> 5.0" }
archive = { source = "hashicorp/archive", version = "~> 2.2.0" }
```
- `~> 5.0` means "any 5.x version, but not 6.0". AWS provider v5 still works with Terraform 0.13, while v6 needs Terraform 1.x.
- The `archive` provider is what builds the Lambda zip files.

### 5.3 `terraform/providers.tf`: region and tags

```hcl
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "Onboarding" }
  }
}
```
`default_tags` adds `Project = Onboarding` to **every** resource that supports tags, across all modules. That is how the "tag everything" rule is met without repeating the tag in every resource.

### 5.4 `terraform/variables.tf`: the inputs

Declares the five inputs: `name_prefix`, `owner`, `aws_region`, `input_prefix` (default `input/`) and `output_prefix` (default `output/`).

`name_prefix` and `owner` include a **validation** rule, a regular expression check, so a typo such as an uppercase letter is caught before anything is created:

```hcl
validation {
  condition     = can(regex("^[a-z0-9]+$", var.owner))
  error_message = "The owner value must be lowercase letters or digits only."
}
```
S3 bucket names must be lowercase, which is why this matters.

### 5.5 `terraform/main.tf`: the root module

The assignment says the root module may **only call modules**, so this file contains no resources. Think of it as the wiring diagram.

**The naming rule** is built once:
```hcl
locals {
  name = "${var.name_prefix}-onboarding-${var.owner}"   # → "aw1dd-onboarding-amitra"
}
```
Every module call then adds a suffix: `"${local.name}-s3-bucket"`, `"${local.name}-sns-topic"`, and so on.

**Modules are connected through outputs.** For example:
```hcl
module "sqs_queue" {
  source        = "./modules/sqs_queue"
  queue_name    = "${local.name}-sqs-queue"
  sns_topic_arn = module.sns_topic.topic_arn      # ← output of the sns_topic module
}
```
Because `sqs_queue` uses an output of `sns_topic`, Terraform knows it must create the topic first. You never write the order by hand; Terraform works it out from these references.

**The same Lambda module is used twice**, with different settings:

| Setting | `module "read_lambda"` | `module "write_lambda"` |
|---|---|---|
| `source_dir` | `lambdas/read_lambda` | `lambdas/write_lambda` |
| `timeout` | 60 seconds (files can be big) | 30 seconds |
| `environment_variables` | `BUCKET_NAME`, `SNS_TOPIC_ARN` | `BUCKET_NAME`, `OUTPUT_PREFIX` |
| `policy_statements` | read `input/*` from S3, publish to SNS | write `output/*` to S3 |
| `sqs_event_source` | not set (S3 triggers it instead) | the queue, 10 messages per batch |

The **environment variables** are how the Python code learns the bucket name and topic ARN without hard-coding them. The **policy statements** give each Lambda only the permissions it needs; for example read-lambda can read only `input/*`, not `output/*`.

### 5.6 `modules/s3_bucket`

Creates three resources:

| Resource | Purpose |
|---|---|
| `aws_s3_bucket` | The bucket. `force_destroy = true` lets `terraform destroy` delete it even when it still contains files. |
| `aws_s3_bucket_public_access_block` | Blocks every form of public access, so files can never be exposed to the internet by mistake. |
| `aws_s3_bucket_server_side_encryption_configuration` | Encrypts every file at rest with AES-256. |

Outputs: `bucket_name`, `bucket_arn`.

### 5.7 `modules/sns_topic`

A single `aws_sns_topic`. Output: `topic_arn`.

### 5.8 `modules/sqs_queue`

| Resource | Purpose |
|---|---|
| `aws_sqs_queue.dlq` | The dead-letter queue (name ends in `-dlq`). Keeps failed messages for 14 days, the maximum. |
| `aws_sqs_queue.this` | The main queue. Its `redrive_policy` says *"after 3 failed receives (`maxReceiveCount`), move the message to the DLQ."* `visibility_timeout_seconds = 180` hides a message from other consumers for 3 minutes while one Lambda works on it; this must be longer than the Lambda's timeout. |
| `aws_sqs_queue_policy` | A *resource policy* on the queue: "SNS may send messages here, **but only from our topic**" (the `aws:SourceArn` condition). Without it SNS cannot deliver to the queue. |
| `aws_sns_topic_subscription` | Subscribes the queue to the topic. `raw_message_delivery = true` is important; see below. |

**What `raw_message_delivery` does.** Without it, SNS wraps every message in a large JSON "envelope" with metadata, and our real data is buried inside as an escaped string. With raw delivery turned on:
- the SQS message body **is** our JSON, so write-lambda can use it directly, and
- the SNS message attributes (`source_key`, `line_number`) are copied to the SQS message, so write-lambda can build file names from them.

`depends_on = [aws_sqs_queue_policy.this]` makes sure the permission exists before the subscription starts sending messages.

Outputs: `queue_arn`, `queue_url`, `dlq_arn`.

### 5.9 `modules/lambda_function`: the shared module

This module is used for **both** Lambdas. It contains everything a Lambda needs:

| Block | What it does |
|---|---|
| `data "archive_file"` | Zips the Python folder (e.g. `lambdas/read_lambda/`) into `terraform/build/<name>.zip`. |
| `aws_iam_role` | The Lambda's identity. The `assume_role_policy` says *only the Lambda service* may use this role. |
| `locals` | Builds the permission statements: a **logging** statement (write to its own log group only) plus any extra statements passed in through `policy_statements`. |
| `aws_iam_role_policy.this` | Attaches those permissions to the role. |
| `aws_iam_role_policy.sqs` | Only created when `sqs_event_source` is set (`count = ... ? 0 : 1`). Lets the Lambda receive and delete messages from that queue. |
| `aws_cloudwatch_log_group` | The log group `/aws/lambda/<function name>`, keeping logs for 14 days. Creating it ourselves (instead of letting AWS create it) lets us set retention and lets Terraform delete it later. |
| `aws_lambda_function` | The function itself: runtime `python3.9`, handler `handler.lambda_handler` (meaning *file* `handler.py`, *function* `lambda_handler`), the zip, timeout, memory and environment variables. |
| `aws_lambda_event_source_mapping` | Only when `sqs_event_source` is set. Tells AWS to poll the queue and call the Lambda with batches of messages. `ReportBatchItemFailures` lets the Lambda say which individual messages failed (see [section 7.2](#72-write-lambda-lambdaswrite_lambdahandlerpy)). |

Two details worth knowing:

- **`source_code_hash`** is a fingerprint of the zip. When you change the Python code, the fingerprint changes, and Terraform knows to upload the new code. If the code is unchanged, nothing is uploaded.
- **`count = condition ? 0 : 1`** is the standard Terraform 0.13 way to make a resource optional: `count = 0` means "don't create it".

Outputs: `function_name`, `function_arn`, `role_arn`, `log_group_name`.

### 5.10 `modules/s3_notification`

| Resource | Purpose |
|---|---|
| `aws_lambda_permission` | Lets S3 (and only our bucket, via `source_arn`) invoke read-lambda. Lambdas reject outside callers unless they are allowed explicitly. |
| `aws_s3_bucket_notification` | The rule "on `s3:ObjectCreated:*` with prefix `input/` and suffix `.csv`, call read-lambda". |

This lives in its own module because it needs **both** the bucket and the Lambda to exist first; putting it in either of those modules would create a circular dependency.

### 5.11 `terraform/outputs.tf`

Prints useful values after `apply` (bucket name, topic ARN, queue URL, DLQ ARN, Lambda names). You can read them again any time with `terraform output <name>`.

---

## 6. How values travel through Terraform

Using the value `amitra` as an example:

```
terraform.tfvars        owner = "amitra"
      │  Terraform loads terraform.tfvars automatically
      ▼
variables.tf            variable "owner" { ... }          ← declared and validated
      │
      ▼
main.tf                 local.name = "aw1dd-onboarding-amitra"
      │
      ├─► module "s3_bucket"    bucket_name   = "aw1dd-onboarding-amitra-s3-bucket"
      ├─► module "sns_topic"    topic_name    = "aw1dd-onboarding-amitra-sns-topic"
      ├─► module "sqs_queue"    queue_name    = "aw1dd-onboarding-amitra-sqs-queue"  (+ "-dlq")
      ├─► module "read_lambda"  function_name = "aw1dd-onboarding-amitra-read-lambda"
      └─► module "write_lambda" function_name = "aw1dd-onboarding-amitra-write-lambda"
                                      │
                                      ▼ inside the module
                                role:      aw1dd-onboarding-amitra-read-lambda-role
                                policy:    aw1dd-onboarding-amitra-read-lambda-policy
                                log group: /aws/lambda/aw1dd-onboarding-amitra-read-lambda
```

And the order Terraform creates things in, worked out from the references between modules:

```
s3_bucket ─┬──────────────────────────► read_lambda ──► s3_notification
sns_topic ─┼─► sqs_queue ──► write_lambda
           └──────────────────────────► read_lambda
```

---

## 7. The Python code, line by line

Both files follow the same structure:

1. Read settings from **environment variables** (set by Terraform).
2. Create the boto3 **clients** once, outside the handler, so AWS can reuse them across invocations (faster).
3. `lambda_handler(event, context)` is the **entry point** AWS calls. `event` holds the trigger data; `context` holds runtime info (unused here).

### 7.1 read-lambda (`lambdas/read_lambda/handler.py`)

```python
BUCKET_NAME = os.environ["BUCKET_NAME"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
```
The bucket and topic come from environment variables, as the assignment requires. If one is missing, the Lambda fails immediately with a clear error.

**`lambda_handler`**: S3 can send several records in one event, so it loops over `event["Records"]`.
```python
key = unquote_plus(record["s3"]["object"]["key"])
```
S3 *URL-encodes* keys in events (a space becomes `+`), so `unquote_plus` turns `my+file.csv` back into `my file.csv`. It also skips events from any other bucket as a safety check.

**`process_csv`**: reads and converts the file.
```python
body = s3.get_object(Bucket=bucket, Key=key)["Body"]
reader = csv.DictReader(codecs.getreader("utf-8-sig")(body))
```
- The file is **streamed**: lines are read as they download, so even a large CSV does not have to fit in memory.
- `utf-8-sig` silently removes the invisible "BOM" character that Excel often adds to the start of CSV files.
- `csv.DictReader` uses the header row as keys and handles quoted values correctly, so `"Kolkata, WB"` stays one value even though it contains a comma.

```python
for line_number, row in enumerate(reader, start=2):   # line 1 is the header
```
Each `row` is a dictionary like `{"order_id": "1001", "customer": "Rahul Kumar", ...}`.

**`build_entry`**: wraps one row as an SNS message.
```python
"Message": json.dumps(row),                              # the JSON event
"MessageAttributes": {
    "source_key":  {"DataType": "String", "StringValue": source_key},
    "line_number": {"DataType": "Number", "StringValue": str(line_number)},
},
```
The attributes are labels that travel *with* the message; write-lambda uses them to name the output file. If a row has more values than there are headers, the extras are kept under `"_extra"` instead of being lost.

**`publish_batch`**: sends up to 10 messages in **one** API call (SNS's limit), which is much faster than one call per line. If SNS reports any failures, the function raises an error. The Lambda then fails, and S3 automatically retries the whole invocation.

### 7.2 write-lambda (`lambdas/write_lambda/handler.py`)

```python
BUCKET_NAME = os.environ["BUCKET_NAME"]
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "output/")
```

**`lambda_handler`**: SQS sends a batch of up to 10 messages.
```python
failures = []
for record in records:
    try:
        key = save_event(record)
    except Exception:
        logger.exception(...)
        failures.append({"itemIdentifier": message_id})
return {"batchItemFailures": failures}
```
This is **partial batch failure** reporting. If 1 out of 10 messages is broken, only that one is returned to the queue for retry; the 9 good ones are deleted. Without this, one bad message would make all 10 retry.

**`save_event`**: `json.loads(record["body"])` checks the body really is JSON (a broken message fails here), then `s3.put_object` saves it with `ContentType="application/json"`.

**`object_key`**: decides the file name.
```python
source_name = posixpath.splitext(posixpath.basename(source_key))[0]   # "input/sample.csv" → "sample"
return f"{OUTPUT_PREFIX}{source_name}/{int(line_number):06d}.json"     # → "output/sample/000002.json"
```
- `:06d` pads the number with zeros (`2` → `000002`) so files sort in the right order.
- If the attributes are missing (for example, someone sends a message to the queue by hand), it falls back to the unique SQS message ID: `output/<message-id>.json`.

### 7.3 Logging

Both files use Python's `logging` module. The level defaults to `INFO` and can be changed with a `LOG_LEVEL` environment variable. Typical CloudWatch output:

```
[INFO] Received S3 event with 1 record(s)
[INFO] Reading s3://aw1dd-onboarding-amitra-s3-bucket/input/sample.csv
[INFO] Published 5 event(s) from s3://.../input/sample.csv
...
[INFO] Received 2 SQS message(s)
[INFO] Saved message 9a07... to s3://.../output/sample/000003.json
[INFO] Saved 2 of 2 message(s)
```

---

## 8. The tests

The tests are in `lambdas/tests/` and run **without AWS**: no account and no internet needed.

- **`conftest.py`** provides a helper, `load_handler`, that sets the environment variables, replaces `boto3` with a **fake** (a `MagicMock`) and then imports the handler. The fake records every call, so a test can check, for example, "was `put_object` called with key `output/people/000002.json`?". It also turns off `__pycache__` creation, so cache files don't end up inside the Lambda zip.
- **`test_read_lambda.py`** (5 tests):
  - one message per line;
  - BOM and quoted commas handled;
  - URL-encoded key decoded;
  - batches of exactly 10;
  - extra columns kept;
  - SNS failure raises an error;
  - other buckets ignored.
- **`test_write_lambda.py`** (3 tests): the correct file name and content; the fallback name; only the broken message reported as failed.

Run them:
```sh
pip install pytest
python -m pytest lambdas/tests                                   # all tests
python -m pytest lambdas/tests/test_write_lambda.py              # one file
python -m pytest lambdas/tests/test_read_lambda.py::test_publishes_in_batches_of_ten   # one test
```

---

## 9. Design decisions and why we made them

| Decision | Why |
|---|---|
| **Separate `input/` and `output/` folders** | Both Lambdas use the same bucket. If write-lambda's files could trigger read-lambda, the system would loop forever. The S3 trigger only fires for `input/*.csv`, and write-lambda only writes to `output/`. |
| **File names from file + line number** | SQS can deliver the same message more than once. Because the name is always the same for the same line, a duplicate just overwrites the file instead of creating a copy (this property is called *idempotent*). |
| **Dead-letter queue** | A broken message is retried 3 times, then parked in the DLQ where someone can inspect it, instead of retrying forever and wasting money. |
| **Least-privilege IAM** | Each Lambda can do only its own job: read-lambda can't write to S3, write-lambda can't read `input/` or publish to SNS. If one is compromised or buggy, the damage is limited. |
| **Private, encrypted bucket** | Public access is blocked and files are encrypted at rest. These are safe defaults that cost nothing. |
| **One shared Lambda module** | Required by the assignment, and it avoids copy-paste: role, policy, logs and trigger are written once and reused. |
| **Root module only calls modules** | Required by the assignment. It keeps `main.tf` a readable "wiring diagram". |
| **`default_tags`** | Tags every resource in one place, so nobody can forget the tag on a new resource. |
| **State committed to git** | Required by the assignment. In real teams state usually lives in an S3 bucket with locking (DynamoDB), because a file in git can't stop two people running `apply` at the same time. |

---

## 10. How to run everything

### Prerequisites

- Terraform **0.13.7** on your `PATH` (`required_version` in `versions.tf` refuses other versions).
- AWS CLI configured with credentials (`aws sts get-caller-identity` should print your account).

### Deploy

```sh
cd terraform
terraform init                     # downloads providers, sets up the backend
terraform plan -out=x.tfplan       # shows what will be created; read it!
terraform apply x.tfplan           # creates exactly what the plan showed
git add state/terraform.tfstate && git commit -m "Update state"
```
Saving the plan to a file and applying *that file* guarantees that what you reviewed is exactly what gets applied.

### Try it

```sh
aws s3 cp sample-data/sample.csv s3://aw1dd-onboarding-amitra-s3-bucket/input/sample.csv
aws s3 ls s3://aw1dd-onboarding-amitra-s3-bucket/output/sample/
aws s3 cp s3://aw1dd-onboarding-amitra-s3-bucket/output/sample/000002.json -
```

To see the logs, open CloudWatch → Log groups → `/aws/lambda/aw1dd-onboarding-amitra-read-lambda` (or `-write-lambda`) in the AWS Console.

### Change something

- **Python code:** edit `lambdas/.../handler.py`, run the tests, then `plan` / `apply`. Terraform notices the new code through `source_code_hash`.
- **Names:** edit `owner` or `name_prefix` in `terraform.tfvars`. AWS cannot rename these resources, so Terraform deletes and recreates them all.

### Tear down

```sh
cd terraform
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
git add state/terraform.tfstate && git commit -m "Destroy infrastructure"
```

---

## 11. Questions teammates are likely to ask

**Why does read-lambda publish to SNS instead of writing the JSON files itself?**
The assignment requires this flow, and it is a common real-world pattern. Splitting reading from writing means each part can scale, fail and retry independently, and other systems can subscribe to the same topic later without changing read-lambda.

**What if the same CSV is uploaded twice?**
It is processed again and the JSON files are overwritten with the same content, so there are no duplicates.

**What if a CSV has 10,000 lines?**
read-lambda streams the file and publishes 10 lines per API call, so memory stays low. Its timeout is 60 seconds; for very large files you would increase `timeout` in `main.tf`. write-lambda scales out automatically, with several copies running in parallel.

**Where do I look when something goes wrong?**
1. The CloudWatch logs of read-lambda: did it run, and how many events did it publish?
2. The CloudWatch logs of write-lambda: look for `[ERROR]` lines.
3. The DLQ (`aw1dd-onboarding-amitra-sqs-queue-dlq`): failed messages wait there for up to 14 days.

**Where do the variable values come from?**
From `terraform/terraform.tfvars`, which Terraform loads automatically. With more environments (dev/test/prod), each would get its own file (e.g. `prod.tfvars`) passed with `-var-file=prod.tfvars`.

**Why AWS provider v5 with an old Terraform (0.13.7)?**
v5 is the newest provider version that still supports Terraform 0.13. Older providers (v3) can't use the newer S3 resources used here.

**Is anything secret stored in the repo?**
No. The state file contains the AWS account ID and resource names and ARNs, but no passwords or access keys. The Lambdas get their AWS permissions from their IAM roles, not from stored keys.
