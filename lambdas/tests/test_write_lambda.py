import json

import pytest

ENV = {"BUCKET_NAME": "test-bucket", "OUTPUT_PREFIX": "output/"}


@pytest.fixture
def write_lambda(load_handler):
    return load_handler("write_lambda", ENV)


def sqs_record(message_id, body, source_key=None, line_number=None):
    attributes = {}
    if source_key:
        attributes["source_key"] = {"stringValue": source_key, "dataType": "String"}
    if line_number:
        attributes["line_number"] = {"stringValue": str(line_number), "dataType": "Number"}
    return {"messageId": message_id, "body": body, "messageAttributes": attributes}


def test_saves_each_message_as_a_file(write_lambda):
    module, clients = write_lambda
    event = {
        "Records": [
            sqs_record("m1", '{"id": "1"}', "input/people.csv", 2),
            sqs_record("m2", '{"id": "2"}', "input/people.csv", 3),
        ]
    }

    result = module.lambda_handler(event, None)

    calls = clients["s3"].put_object.call_args_list
    assert [c.kwargs["Key"] for c in calls] == ["output/people/000002.json", "output/people/000003.json"]
    assert json.loads(calls[0].kwargs["Body"]) == {"id": "1"}
    assert calls[0].kwargs["Bucket"] == "test-bucket"
    assert result == {"batchItemFailures": []}


def test_falls_back_to_message_id_key(write_lambda):
    module, clients = write_lambda

    module.lambda_handler({"Records": [sqs_record("abc-123", '{"x": 1}')]}, None)

    assert clients["s3"].put_object.call_args.kwargs["Key"] == "output/abc-123.json"


def test_reports_only_failed_messages(write_lambda):
    module, clients = write_lambda
    event = {"Records": [sqs_record("good", '{"ok": true}'), sqs_record("bad", "not json")]}

    result = module.lambda_handler(event, None)

    assert result == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert clients["s3"].put_object.call_count == 1
