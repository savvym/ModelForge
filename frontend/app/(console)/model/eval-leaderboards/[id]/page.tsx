import { redirect } from "next/navigation";

export default function BenchmarkLeaderboardDetailPage() {
  redirect("/model/eval?tab=runs");
}
