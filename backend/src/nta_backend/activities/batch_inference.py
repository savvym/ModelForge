from temporalio import activity


@activity.defn
async def validate_batch_input(payload: dict) -> dict[str, str]:
    return {"status": "validated", "input_object_key": payload["input_object_key"]}


@activity.defn
async def run_batch_inference_chunks(payload: dict) -> dict[str, int | str]:
    return {
        "status": "completed",
        "processed": 20,
        "output_object_key": payload["output_object_key"],
    }


@activity.defn
async def merge_batch_outputs(payload: dict) -> dict[str, str]:
    return {"status": "merged", "output_object_key": payload["output_object_key"]}
