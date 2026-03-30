import { ConsolePage } from "@/components/console/console-page";

export default function EndpointPage() {
  return (
    <ConsolePage
      pageKey="endpoint"
      highlight="在线推理建议拆成预置接入点和自定义接入点两个 tab，再接入数据表格和 SSE 状态刷新。"
    />
  );
}
