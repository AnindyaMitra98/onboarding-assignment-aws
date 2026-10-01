import importlib.util
import pathlib
import sys
import types
from unittest import mock

import pytest

# Keep __pycache__ out of the Lambda source dirs that Terraform zips.
sys.dont_write_bytecode = True

LAMBDAS_DIR = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def load_handler(monkeypatch):
    """Import a Lambda handler with a mocked boto3 and the given environment."""

    def _load(lambda_dir, env):
        for name, value in env.items():
            monkeypatch.setenv(name, value)

        clients = {}
        fake_boto3 = types.ModuleType("boto3")
        fake_boto3.client = lambda service, **_: clients.setdefault(service, mock.MagicMock())
        monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

        path = LAMBDAS_DIR / lambda_dir / "handler.py"
        spec = importlib.util.spec_from_file_location(f"{lambda_dir}_handler", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, clients

    return _load
