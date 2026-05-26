from datetime import UTC, datetime
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
from nta_backend.services.model_deployment_service import (
    ModelDeploymentService,
    _redact_spec,
    _serialize_deployment_task,
)


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
    assert spec.engine.extra_args == {
        "reasoning_parser": "qwen3",
    }
    assert _redact_spec(spec)["engine"]["api_key"] == "********"


def test_build_spec_prefers_explicit_deployment_gpu_ids() -> None:
    model = SimpleNamespace(
        id=uuid4(),
        name="Qwen",
        model_code="qwen",
        capabilities_json={
            "huggingface_import": {
                "repo_id": "Qwen/Qwen2.5",
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
        gpu_ids=[0, 1, 2, 3],
        tensor_parallel_size=2,
        dtype="bfloat16",
        gpu_memory_utilization=0.85,
        max_model_len=None,
        listen_port=8000,
    )

    spec = ModelDeploymentService()._build_spec(
        model,  # type: ignore[arg-type]
        DeployModelRequest(gpu_ids=[2, 3], tensor_parallel_size=2),
        inference_machine=machine,
        system_huggingface_config={},
    )

    assert spec.engine.gpu_ids == [2, 3]
    assert spec.engine.tensor_parallel_size == 2


def test_build_spec_adds_lora_adapter_binding() -> None:
    model = SimpleNamespace(
        id=uuid4(),
        name="Qwen",
        model_code="qwen",
        capabilities_json={
            "huggingface_import": {
                "repo_id": "Qwen/Qwen2.5",
                "revision": "main",
            }
        },
    )
    adapter_model = SimpleNamespace(
        id=uuid4(),
        name="Customer SFT",
        model_code="customer-sft",
        capabilities_json={
            "object_storage_import": {
                "artifact_type": "lora_adapter",
                "source_uri": "s3://models/customer-sft/",
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
        DeployModelRequest(adapter_model_id=adapter_model.id),
        inference_machine=machine,
        system_huggingface_config={},
        adapter_model=adapter_model,  # type: ignore[arg-type]
    )

    assert spec.model.served_name == "qwen"
    assert len(spec.lora_adapters) == 1
    assert spec.lora_adapters[0].adapter_id == str(adapter_model.id)
    assert spec.lora_adapters[0].served_name == "customer-sft"
    assert spec.lora_adapters[0].source.uri == "s3://models/customer-sft/"


def test_build_spec_requires_explicit_gpu_count_to_match_tp() -> None:
    model = SimpleNamespace(
        id=uuid4(),
        name="Qwen",
        model_code="qwen",
        capabilities_json={
            "huggingface_import": {
                "repo_id": "Qwen/Qwen2.5",
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
        gpu_ids=[0, 1, 2, 3],
        tensor_parallel_size=2,
        dtype="bfloat16",
        gpu_memory_utilization=0.85,
        max_model_len=None,
        listen_port=8000,
    )

    with pytest.raises(ValueError, match="GPU 数量"):
        ModelDeploymentService()._build_spec(
            model,  # type: ignore[arg-type]
            DeployModelRequest(gpu_ids=[2], tensor_parallel_size=2),
            inference_machine=machine,
            system_huggingface_config={},
        )


def test_build_spec_leaves_plain_models_without_reasoning_parser_args() -> None:
    model = SimpleNamespace(
        id=uuid4(),
        name="Qwen2.5 Instruct",
        model_code="qwen2.5-instruct",
        capabilities_json={
            "huggingface_import": {
                "repo_id": "Qwen/Qwen2.5-7B-Instruct",
                "revision": "main",
                "deployment_hints": {
                    "model_type": "qwen2",
                    "architectures": ["Qwen2ForCausalLM"],
                },
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

    assert spec.engine.extra_args == {}


def test_build_spec_enables_lora_for_gemma4_architecture() -> None:
    model = SimpleNamespace(
        id=uuid4(),
        name="Gemma 4",
        model_code="gemma-4",
        capabilities_json={
            "huggingface_import": {
                "repo_id": "google/gemma-4-31B",
                "revision": "main",
                "deployment_hints": {
                    "model_type": "gemma4",
                    "architectures": ["Gemma4ForConditionalGeneration"],
                },
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
        gpu_ids=list(range(8)),
        tensor_parallel_size=8,
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

    assert spec.engine.enable_lora is True


def test_serialize_deployment_task_keeps_superseded_task_terminal() -> None:
    endpoint_id = uuid4()
    endpoint = SimpleNamespace(
        id=endpoint_id,
        name="Qwen 部署",
        model_id=uuid4(),
        status="stopped",
        endpoint_type="infer-agent-vllm",
        config_json={
            "generation": 2,
            "agent_status": {
                "phase": "superseded",
                "progress": 100,
                "last_event": "已被同一推理机器上的新部署替换",
            },
        },
        created_at=datetime(2026, 4, 23, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 23, 0, 1, tzinfo=UTC),
    )

    task = _serialize_deployment_task(endpoint)  # type: ignore[arg-type]

    assert task.id == endpoint_id
    assert task.status == "stopped"
    assert task.phase == "superseded"
    assert task.progress == 100
