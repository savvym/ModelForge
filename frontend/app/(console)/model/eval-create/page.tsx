import { redirect } from "next/navigation";

export default function ModelEvalCreatePage() {
  redirect("/model/eval?tab=jobs&create=1");
}
