import { ConsolePage } from "@/components/console/console-page";

export default function BatchInferencePage() {
  return (
    <ConsolePage
      pageKey="batch-inference"
      highlight="批量推理建议使用任务 / 接入点双 tab，并把 Temporal 工作流状态通过 SSE 透出到表格。"
    />
  );
}
