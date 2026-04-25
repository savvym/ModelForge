import {
  getSystemHuggingFaceSettings,
  getSystemTrainingCosSettings
} from "@/features/system-config/api";
import { SystemConfigConsole } from "@/features/system-config/components/system-config-console";

export default async function SystemConfigPage() {
  const [huggingFaceSettings, trainingCosSettings] = await Promise.all([
    getSystemHuggingFaceSettings().catch(() => ({
      endpoint_url: null,
      token: null,
      has_token: false
    })),
    getSystemTrainingCosSettings().catch(() => ({
      enabled: false,
      protocol: "http",
      endpoint: null,
      endpoint_url: null,
      region: null,
      bucket: null,
      bucket_alias: null,
      target_prefix: "training/datasets",
      addressing_style: "virtual",
      hosts: null,
      has_secret_id: false,
      has_secret_key: false,
      has_session_token: false,
      secret_id_masked: null,
      secret_key_masked: null,
      session_token_masked: null
    }))
  ]);

  return (
    <SystemConfigConsole
      initialHuggingFaceSettings={huggingFaceSettings}
      initialTrainingCosSettings={trainingCosSettings}
    />
  );
}
