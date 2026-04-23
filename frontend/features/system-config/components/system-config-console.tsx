"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, RefreshCcw, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ConsoleListHeader } from "@/components/console/list-surface";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getSystemHuggingFaceSettings,
  updateSystemHuggingFaceSettings
} from "@/features/system-config/api";
import type { SystemHuggingFaceSettings } from "@/types/api";

export function SystemConfigConsole({
  initialHuggingFaceSettings
}: {
  initialHuggingFaceSettings: SystemHuggingFaceSettings;
}) {
  const router = useRouter();
  const [settings, setSettings] = useState(initialHuggingFaceSettings);
  const [form, setForm] = useState({
    endpoint_url: initialHuggingFaceSettings.endpoint_url ?? "",
    token: initialHuggingFaceSettings.token ?? ""
  });
  const [showToken, setShowToken] = useState(false);
  const [pending, setPending] = useState(false);

  async function refreshSettings() {
    setPending(true);
    try {
      const nextSettings = await getSystemHuggingFaceSettings();
      setSettings(nextSettings);
      setForm({
        endpoint_url: nextSettings.endpoint_url ?? "",
        token: nextSettings.token ?? ""
      });
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "刷新系统配置失败。");
    } finally {
      setPending(false);
    }
  }

  async function saveSettings(clearToken = false) {
    setPending(true);
    try {
      const nextSettings = await updateSystemHuggingFaceSettings({
        clear_token: clearToken,
        endpoint_url: form.endpoint_url.trim() || null,
        token: clearToken ? null : form.token.trim() || null
      });
      setSettings(nextSettings);
      setForm({
        endpoint_url: nextSettings.endpoint_url ?? "",
        token: nextSettings.token ?? ""
      });
      setShowToken(false);
      toast.success(clearToken ? "HF Token 已清除。" : "配置已保存。");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存系统配置失败。");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-5">
      <ConsoleListHeader
        actions={
          <Button
            disabled={pending}
            onClick={() => void refreshSettings()}
            size="sm"
            type="button"
            variant="outline"
          >
            <RefreshCcw className="mr-2 h-4 w-4" />
            刷新
          </Button>
        }
        description="管理控制面全局集成配置，模型搜索、录入校验和 infer-agent 部署会继承这里的 Hugging Face 配置。"
        title="系统配置"
      />

      <section className="grid gap-5 rounded-lg border border-border bg-card/70 p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
          <div className="space-y-1">
            <h2 className="text-base font-semibold text-foreground">Hugging Face</h2>
            <p className="text-sm leading-6 text-muted-foreground">
              全局 Token 会用于 HF 搜索、私有/ gated 模型权限校验，以及 H20 推理机器下载模型。
            </p>
          </div>
          <div className="rounded-full border border-border bg-background/60 px-3 py-1 text-xs text-muted-foreground">
            {settings.has_token ? "Token 已配置" : "Token 未配置"}
          </div>
        </div>

        <div className="grid gap-5 lg:max-w-3xl">
          <div className="space-y-2">
            <Label className="text-foreground" htmlFor="system-hf-endpoint-url">
              Endpoint URL
            </Label>
            <Input
              id="system-hf-endpoint-url"
              onChange={(event) =>
                setForm((current) => ({ ...current, endpoint_url: event.target.value }))
              }
              placeholder="https://huggingface.co"
              value={form.endpoint_url}
            />
            <div className="text-xs text-muted-foreground">
              留空时使用 Hugging Face 官方地址；需要镜像源时填入完整地址。
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-foreground" htmlFor="system-hf-token">
              HF Token
            </Label>
            <div className="flex gap-2">
              <Input
                autoComplete="off"
                className="font-mono text-xs"
                id="system-hf-token"
                onChange={(event) =>
                  setForm((current) => ({ ...current, token: event.target.value }))
                }
                placeholder="hf_xxx"
                type={showToken ? "text" : "password"}
                value={form.token}
              />
              <Button
                aria-label={showToken ? "隐藏 HF Token" : "查看 HF Token"}
                className="shrink-0"
                onClick={() => setShowToken((current) => !current)}
                size="icon"
                type="button"
                variant="outline"
              >
                {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
            <div className="text-xs text-muted-foreground">
              建议使用 Hugging Face fine-grained read token；页面会按你的要求支持明文查看。
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
          <Button
            disabled={pending || !settings.has_token}
            onClick={() => void saveSettings(true)}
            type="button"
            variant="outline"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            清除 Token
          </Button>
          <Button disabled={pending} onClick={() => void saveSettings(false)} type="button">
            <Save className="mr-2 h-4 w-4" />
            {pending ? "保存中..." : "保存配置"}
          </Button>
        </div>
      </section>
    </div>
  );
}
