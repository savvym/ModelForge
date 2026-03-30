import { redirect } from "next/navigation";

export default async function ModelEvalTemplatesRedirectPage() {
  redirect("/model/eval?tab=templates");
}
