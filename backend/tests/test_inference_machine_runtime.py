from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from nta_backend.schemas.model_deployment import DeployModelRequest, InferenceMachineCreate
from nta_backend.services.inference_machine_service import (
    InferenceMachineRuntimeConfig,
    machine_runtime_config,
    runtime_headers,
)
from nta_backend.services.model_deployment_service import ModelDeploymentService, _redact_spec


def test_inference_machine_create_requires_runtime_api_key() -> None:
    with pytest.raises(ValidationError, match="runtime_api_key"):
        InferenceMachineCreate(
            name="h20-node-01",
            agent_base_url="http://10.0.0.12:9000",
            agent_token="agent-token",
            runtime_api_key=" ",
        )


def test_machine_runtime_config_reads_required_runtime_api_key() -> None:
    machine = SimpleNamespace(
        id=uuid4(),
        name="h20-node-01",
        agent_base_url="http://10.0.0.12:9000/",
        agent_token=" agent-token ",
        runtime_public_host="10.0.0.12",
        config_json={
            "runtime_api_key": " runtime-token ",
            "vllm_image": "vllm/vllm-openai:latest",
            "gpu_ids": [0, 1],
            "tensor_parallel_size": 2,
            "dtype": "bfloat16",
            "gpu_memory_utilization": 0.85,
            "listen_port": 8000,
        },
    )

    runtime = machine_runtime_config(machine)  # type: ignore[arg-type]

    assert runtime.agent_token == "agent-token"
    assert runtime.runtime_api_key == "runtime-token"
    assert runtime_headers(runtime) == {"Authorization": "Bearer runtime-token"}


def test_build_spec_downstreams_runtime_api_key_and_redacts_it() -> None:
    model = SimpleNamespace(
        id=uuid4(),
        name="Qwen",
        model_code="qwen",
        capabilities_json={
            "huggingface_import": {
                "repo_id": "Qwen/Qwen3",
                "revision": "main",
            }
        },
    )
    machine = InferenceMachineRuntimeConfig(
        id=uuid4(),
        name="h20-node-01",
        agent_base_url="http://10.0.0.12:9000",
        agent_token="agent-token",
        runtime_api_key="runtime-token",
        runtime_public_host="10.0.0.12",
        vllm_image="vllm/vllm-openai:latest",
        gpu_ids=[0, 1],
        tensor_parallel_size=2,
        dtype="bfloat16",
        gpu_memory_utilization=0.85,
        max_model_len=None,
        listen_port=8000,
    )

    spec = ModelDeploymentService()._build_spec(
        model,  # type: ignore[arg-type]
        DeployModelRequest(),
        inference_machine=machine,
        system_huggingface_config={},
    )

    assert spec.engine.api_key == "runtime-token"
    assert _redact_spec(spec)["engine"]["api_key"] == "********"
