import { getSystemHuggingFaceSettings } from "@/features/system-config/api";
import { SystemConfigConsole } from "@/features/system-config/components/system-config-console";

export default async function SystemConfigPage() {
  const huggingFaceSettings = await getSystemHuggingFaceSettings().catch(() => ({
    endpoint_url: null,
    token: null,
    has_token: false
  }));

  return <SystemConfigConsole initialHuggingFaceSettings={huggingFaceSettings} />;
}
