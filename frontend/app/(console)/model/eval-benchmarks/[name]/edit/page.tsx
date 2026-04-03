import { redirect } from "next/navigation";

export default function EditBenchmarkPage() {
  redirect("/model/eval?tab=catalog");
}
