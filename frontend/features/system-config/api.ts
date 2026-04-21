import { apiFetch } from "@/lib/api-client/http";
import type {
  SystemHuggingFaceSettings,
  SystemHuggingFaceSettingsUpdateInput
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
