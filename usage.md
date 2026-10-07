# Usage Guide

This guide walks you through running the project from scratch: installing the tools, deploying it to AWS, testing it, and removing it again. You don't need to know Terraform or Lambda to follow it. Run the commands in order.

## What the project does

You upload a CSV file to an S3 bucket. The project reads each row and saves it as its own JSON file in the same bucket.

```
You upload:   input/sample.csv          (a header line + 5 rows)
You get:      output/sample/000002.json
              output/sample/000003.json
              ...
              output/sample/000006.json (one file per row, named by its line number)
```

Behind the scenes: **S3 → read-lambda → SNS → SQS → write-lambda → S3**. Terraform creates all of these AWS resources for you.

---

## Step 1 – Check what you need

You need:

1. **An AWS account** and an access key (Access Key ID + Secret Access Key) that is allowed to create S3, SNS, SQS, Lambda, IAM and CloudWatch Logs resources.
2. **A computer** running Windows, macOS or Linux, with internet access.
3. **About 30 minutes** the first time.

> **Cost:** for a few small test files this stays within (or very close to) the AWS free tier. Remember to do [Step 9](#step-9--remove-everything-when-you-are-done) when you are finished so nothing keeps running.

---

## Step 2 – Install the tools

Install each tool below, then open a **new** terminal and run the check command to confirm it works.

| Tool | Version | Where to get it | Check command |
|------|---------|-----------------|---------------|
| Git | any | https://git-scm.com/downloads | `git --version` |
| AWS CLI | v2 | https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html | `aws --version` |
| Terraform | **exactly 0.13.7** | see below | `terraform version` |
| Python *(only for Step 8, optional)* | 3.9 | https://www.python.org/downloads/ | `python --version` |

### Installing Terraform 0.13.7

The project only works with Terraform **0.13.7**. A newer Terraform will stop with an error like `Unsupported Terraform Core version`.

1. Open https://releases.hashicorp.com/terraform/0.13.7/
2. Download the zip for your computer:
   - Windows: `terraform_0.13.7_windows_amd64.zip`
   - macOS (Intel or Apple Silicon): `terraform_0.13.7_darwin_amd64.zip` (on Apple Silicon this runs through Rosetta)
   - Linux: `terraform_0.13.7_linux_amd64.zip`
3. Unzip it. You get a single file: `terraform` (or `terraform.exe` on Windows).
4. Put that file in a folder that is on your `PATH`:
   - **Windows:** create `C:\terraform-0.13.7\`, move `terraform.exe` there, then search the Start menu for *"Edit the system environment variables"* → *Environment Variables* → select `Path` → *Edit* → *New* → `C:\terraform-0.13.7` → move it to the **top** → OK.
   - **macOS / Linux:** `sudo mv terraform /usr/local/bin/terraform`
5. Open a new terminal and run `terraform version`. It must print `Terraform v0.13.7`.

> If you already have a newer Terraform installed, make sure the 0.13.7 folder comes **first** on your `PATH`, or `terraform version` will show the newer one.

---

## Step 3 – Connect the AWS CLI to your account

Run:

```sh
aws configure
```

Answer the four questions:

```
AWS Access Key ID [None]:      <your access key id>
AWS Secret Access Key [None]:  <your secret access key>
Default region name [None]:    us-east-1
Default output format [None]:  json
```

Check that it worked:

```sh
aws sts get-caller-identity
```

You should see your account number. If you see an error, the access key is wrong or not active.

> Terraform uses these same credentials automatically, so you don't need to enter them anywhere else.

---

## Step 4 – Download the project

```sh
git clone https://github.com/AnindyaMitra98/onboarding-assignment-aws.git
cd onboarding-assignment-aws
```

All the commands below assume you are in this `onboarding-assignment-aws` folder unless stated otherwise.

---

## Step 5 – Set your own names

Open `terraform/terraform.tfvars` in any text editor. It looks like this:

```hcl
name_prefix = "aw1dd"
owner       = "amitra"
aws_region  = "us-east-1"
```

- **`owner`** – change this to **your** first initial + last name, all lowercase, letters and digits only. Example: *Rahul Kumar* → `"rkumar"`.
- **`name_prefix`** – keep `"aw1dd"` unless you were given a different prefix.
- **`aws_region`** – the AWS region to deploy into. Keep `"us-east-1"` unless you have a reason to change it.

Every resource will be named `<name_prefix>-onboarding-<owner>-<resource>`. For example, the bucket becomes `aw1dd-onboarding-rkumar-s3-bucket`.

> **Why change `owner`?** S3 bucket names are unique across *all* AWS accounts in the world. If you keep someone else's `owner`, the bucket name may already be taken and Step 6 will fail with `BucketAlreadyExists`.

Save the file.

---

## Step 6 – Deploy to AWS

Go into the `terraform` folder:

```sh
cd terraform
```

**6.1 – Download the Terraform plugins** (only needed the first time):

```sh
terraform init
```

Expected ending: `Terraform has been successfully initialized!`

**6.2 – Check the configuration:**

```sh
terraform validate
```

Expected: `Success! The configuration is valid.`

**6.3 – Preview what will be created:**

```sh
terraform plan -out=x.tfplan
```

This changes nothing yet. Read the summary at the end. On a fresh deployment it should say `Plan: N to add, 0 to change, 0 to destroy.` (some number of resources to add, nothing to change or destroy).

**6.4 – Create the resources:**

```sh
terraform apply x.tfplan
```

This takes 1–2 minutes. Expected ending:

```
Apply complete! Resources: ... added, 0 changed, 0 destroyed.

Outputs:

bucket_name = aw1dd-onboarding-rkumar-s3-bucket
read_lambda_name = aw1dd-onboarding-rkumar-read-lambda
write_lambda_name = aw1dd-onboarding-rkumar-write-lambda
...
```

**Write down the `bucket_name` value** – you need it in the next step. You can show it again at any time with:

```sh
terraform output bucket_name
```

Go back to the project folder:

```sh
cd ..
```

---

## Step 7 – Run it

In the commands below, replace `YOUR-BUCKET` with the `bucket_name` from Step 6.

**7.1 – Upload the sample CSV** into the `input/` folder of the bucket:

```sh
aws s3 cp sample-data/sample.csv s3://YOUR-BUCKET/input/sample.csv
```

**7.2 – Wait about 10–20 seconds**, then list the results:

```sh
aws s3 ls s3://YOUR-BUCKET/output/sample/
```

Expected (5 files – line 1 of the CSV is the header, so numbering starts at 2):

```
... 000002.json
... 000003.json
... 000004.json
... 000005.json
... 000006.json
```

If the list is empty, wait a few more seconds and run it again.

**7.3 – Look at one of the files:**

```sh
aws s3 cp s3://YOUR-BUCKET/output/sample/000002.json -
```

You should see the first data row of the CSV as JSON, for example:

```json
{"order_id": "1001", "customer": "Rahul Kumar", "product": "Laptop", "quantity": "1", "price": "55000.00", "city": "Bengaluru"}
```

**Try your own CSV:** any CSV file with a header row works. Upload it under `input/` and the results appear under `output/<file name without .csv>/`:

```sh
aws s3 cp my-file.csv s3://YOUR-BUCKET/input/my-file.csv
aws s3 ls s3://YOUR-BUCKET/output/my-file/
```

> Only files ending in `.csv` and placed under `input/` are processed. Files anywhere else in the bucket are ignored.

You can also do all of this in the AWS web console: open **S3** → your bucket → create an `input` folder → **Upload** the CSV → then open the `output` folder.

---

## Step 8 – (Optional) Run the unit tests

These tests check the Lambda code on your own computer. They don't touch AWS.

```sh
pip install pytest
python -m pytest lambdas/tests
```

Expected ending: `... passed`.

---

## Step 9 – Remove everything when you are done

This deletes **all** the AWS resources the project created, including the bucket and every file in it.

```sh
cd terraform
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
cd ..
```

Check the plan summary says `0 to add, 0 to change, ... to destroy` before applying. Expected ending: `Apply complete! Resources: 0 added, 0 changed, ... destroyed.`

---

## Troubleshooting

| Problem | What to do |
|---------|------------|
| `Unsupported Terraform Core version` | You are running a newer Terraform. Redo [Step 2](#installing-terraform-0137) and make sure `terraform version` prints `v0.13.7`. |
| `No valid credential sources found` / `ExpiredToken` / `InvalidClientTokenId` | Redo [Step 3](#step-3--connect-the-aws-cli-to-your-account) and check `aws sts get-caller-identity` works. |
| `BucketAlreadyExists` | The bucket name is taken. Change `owner` in `terraform/terraform.tfvars` ([Step 5](#step-5--set-your-own-names)), then rerun Step 6.3 and 6.4. |
| `AccessDenied` during apply | Your AWS user lacks permissions to create S3/SNS/SQS/Lambda/IAM/Logs resources. Ask your AWS administrator. |
| `Saved plan is stale` | Something changed after you ran `plan`. Run `terraform plan -out=x.tfplan` again, then `terraform apply x.tfplan`. |
| No files appear in `output/` | Check the file was uploaded to `input/` and ends in `.csv`. Then check the Lambda logs: AWS console → **CloudWatch** → **Log groups** → `/aws/lambda/<name>-read-lambda` and `/aws/lambda/<name>-write-lambda`. |
| Some rows are missing in `output/` | Rows that failed 3 times are moved to the dead-letter queue. AWS console → **SQS** → queue ending in `-dlq` → **Send and receive messages** → **Poll for messages** to see them. |

---

## Quick reference

```sh
# one-time setup
aws configure
git clone https://github.com/AnindyaMitra98/onboarding-assignment-aws.git
cd onboarding-assignment-aws
# edit terraform/terraform.tfvars -> set owner

# deploy
cd terraform
terraform init
terraform plan -out=x.tfplan
terraform apply x.tfplan
terraform output bucket_name
cd ..

# run
aws s3 cp sample-data/sample.csv s3://YOUR-BUCKET/input/sample.csv
aws s3 ls s3://YOUR-BUCKET/output/sample/

# clean up
cd terraform
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

For an explanation of how the code works, see [PROJECT_GUIDE.md](PROJECT_GUIDE.md). For the project layout and conventions, see [README.md](README.md).
