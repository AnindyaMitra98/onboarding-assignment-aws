import io
import json

import pytest

ENV = {"BUCKET_NAME": "test-bucket", "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:topic"}


def s3_event(key, bucket="test-bucket"):
    return {"Records": [{"s3": {"bucket": {"name": bucket}, "object": {"key": key}}}]}


@pytest.fixture
def read_lambda(load_handler):
    module, clients = load_handler("read_lambda", ENV)
    clients["sns"].publish_batch.return_value = {"Successful": [], "Failed": []}
    return module, clients


def set_csv(clients, text):
    clients["s3"].get_object.return_value = {"Body": io.BytesIO(text.encode("utf-8"))}


def published_entries(clients):
    return [
        entry
        for call in clients["sns"].publish_batch.call_args_list
        for entry in call.kwargs["PublishBatchRequestEntries"]
    ]


def test_publishes_one_message_per_line(read_lambda):
    module, clients = read_lambda
    set_csv(clients, "﻿id,name\n1,Alice\n2,\"Bob, Jr.\"\n")

    result = module.lambda_handler(s3_event("input/people+list.csv"), None)

    clients["s3"].get_object.assert_called_once_with(Bucket="test-bucket", Key="input/people list.csv")
    entries = published_entries(clients)
    assert [json.loads(e["Message"]) for e in entries] == [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob, Jr."},
    ]
    assert entries[0]["MessageAttributes"]["line_number"]["StringValue"] == "2"
    assert entries[0]["MessageAttributes"]["source_key"]["StringValue"] == "input/people list.csv"
    assert result == {"processed": [{"key": "input/people list.csv", "published": 2}]}


def test_publishes_in_batches_of_ten(read_lambda):
    module, clients = read_lambda
    set_csv(clients, "n\n" + "".join(f"{i}\n" for i in range(23)))

    module.lambda_handler(s3_event("input/numbers.csv"), None)

    sizes = [len(c.kwargs["PublishBatchRequestEntries"]) for c in clients["sns"].publish_batch.call_args_list]
    assert sizes == [10, 10, 3]


def test_extra_columns_are_kept(read_lambda):
    module, clients = read_lambda
    set_csv(clients, "a,b\n1,2,3\n")

    module.lambda_handler(s3_event("input/x.csv"), None)

    assert json.loads(published_entries(clients)[0]["Message"]) == {"a": "1", "b": "2", "_extra": ["3"]}


def test_raises_when_publish_fails(read_lambda):
    module, clients = read_lambda
    set_csv(clients, "a\n1\n")
    clients["sns"].publish_batch.return_value = {"Failed": [{"Id": "2", "Code": "InternalError"}]}

    with pytest.raises(RuntimeError):
        module.lambda_handler(s3_event("input/x.csv"), None)


def test_ignores_other_buckets(read_lambda):
    module, clients = read_lambda

    module.lambda_handler(s3_event("input/x.csv", bucket="other-bucket"), None)

    clients["s3"].get_object.assert_not_called()
