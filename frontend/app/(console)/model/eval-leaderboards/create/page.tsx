import { redirect } from "next/navigation";

export default function CreateBenchmarkLeaderboardPage() {
  redirect("/model/eval?tab=runs");
}
