import { redirect } from "next/navigation";

export default function EditBenchmarkVersionPage() {
  redirect("/model/eval?tab=catalog");
}
