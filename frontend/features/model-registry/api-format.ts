export const modelApiFormatOptions = [
  { label: "OpenAI Chat Completions", value: "chat-completions" },
  { label: "OpenAI Responses", value: "responses" },
  { label: "Google Generative AI", value: "google" }
];

export function formatModelApiFormat(value?: string | null) {
  if (value === "responses") {
    return "OpenAI Responses";
  }
  if (value === "google") {
    return "Google Generative AI";
  }
  return "OpenAI Chat";
}
