import { redirect } from "next/navigation";

export default function CreateBenchmarkVersionPage() {
  redirect("/model/eval?tab=catalog");
}
