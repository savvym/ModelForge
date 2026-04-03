import { redirect } from "next/navigation";

export default function CreateBenchmarkPage() {
  redirect("/model/eval?tab=catalog");
}
