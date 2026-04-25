import { apiFetch } from "@/lib/api-client/http";
import type {
  SystemHuggingFaceSettings,
  SystemHuggingFaceSettingsUpdateInput,
  SystemTrainingCosProbeResponse,
  SystemTrainingCosSettings,
  SystemTrainingCosSettingsUpdateInput
} from "@/types/api";

export async function getSystemHuggingFaceSettings(): Promise<SystemHuggingFaceSettings> {
  return apiFetch<SystemHuggingFaceSettings>("/system/config/huggingface");
}

export async function updateSystemHuggingFaceSettings(
  payload: SystemHuggingFaceSettingsUpdateInput
): Promise<SystemHuggingFaceSettings> {
  return apiFetch<SystemHuggingFaceSettings>("/system/config/huggingface", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function getSystemTrainingCosSettings(): Promise<SystemTrainingCosSettings> {
  return apiFetch<SystemTrainingCosSettings>("/system/config/training-cos");
}

export async function updateSystemTrainingCosSettings(
  payload: SystemTrainingCosSettingsUpdateInput
): Promise<SystemTrainingCosSettings> {
  return apiFetch<SystemTrainingCosSettings>("/system/config/training-cos", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function probeSystemTrainingCosSettings(): Promise<SystemTrainingCosProbeResponse> {
  return apiFetch<SystemTrainingCosProbeResponse>("/system/config/training-cos/probe", {
    method: "POST"
  });
}
