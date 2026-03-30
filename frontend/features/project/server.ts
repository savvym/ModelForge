import "server-only";

import { cookies } from "next/headers";
import { CURRENT_PROJECT_COOKIE } from "@/features/project/constants";

export async function getCurrentProjectIdFromCookie(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(CURRENT_PROJECT_COOKIE)?.value ?? null;
}
