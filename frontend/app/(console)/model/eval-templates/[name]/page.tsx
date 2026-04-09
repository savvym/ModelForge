import { redirect } from "next/navigation";

export default function EvalTemplateDetailPage() {
  redirect("/model/eval?tab=dimensions");
}
