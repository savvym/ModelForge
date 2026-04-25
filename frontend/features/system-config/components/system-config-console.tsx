"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Cloud, Eye, EyeOff, PlugZap, RefreshCcw, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ConsoleListHeader } from "@/components/console/list-surface";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  getSystemHuggingFaceSettings,
  getSystemTrainingCosSettings,
  probeSystemTrainingCosSettings,
  updateSystemHuggingFaceSettings,
  updateSystemTrainingCosSettings
} from "@/features/system-config/api";
import type { SystemHuggingFaceSettings, SystemTrainingCosSettings } from "@/types/api";

export function SystemConfigConsole({
  initialHuggingFaceSettings,
  initialTrainingCosSettings
}: {
  initialHuggingFaceSettings: SystemHuggingFaceSettings;
  initialTrainingCosSettings: SystemTrainingCosSettings;
}) {
  const router = useRouter();
  const [settings, setSettings] = useState(initialHuggingFaceSettings);
  const [trainingCosSettings, setTrainingCosSettings] = useState(initialTrainingCosSettings);
  const [form, setForm] = useState({
    endpoint_url: initialHuggingFaceSettings.endpoint_url ?? "",
    token: initialHuggingFaceSettings.token ?? ""
  });
  const [trainingCosForm, setTrainingCosForm] = useState(() =>
    buildTrainingCosForm(initialTrainingCosSettings)
  );
  const [showToken, setShowToken] = useState(false);
  const [showTrainingSecrets, setShowTrainingSecrets] = useState(false);
  const [pending, setPending] = useState(false);
  const [trainingPending, setTrainingPending] = useState(false);
  const [probePending, setProbePending] = useState(false);

  async function refreshSettings() {
    setPending(true);
    try {
      const [nextSettings, nextTrainingCosSettings] = await Promise.all([
        getSystemHuggingFaceSettings(),
        getSystemTrainingCosSettings()
      ]);
      setSettings(nextSettings);
      setTrainingCosSettings(nextTrainingCosSettings);
      setForm({
        endpoint_url: nextSettings.endpoint_url ?? "",
        token: nextSettings.token ?? ""
      });
      setTrainingCosForm(buildTrainingCosForm(nextTrainingCosSettings));
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

  async function saveTrainingCosSettings(clearSecrets = false) {
    setTrainingPending(true);
    try {
      const nextSettings = await updateSystemTrainingCosSettings({
        addressing_style: trainingCosForm.addressing_style.trim() || "virtual",
        bucket: trainingCosForm.bucket.trim() || null,
        bucket_alias: trainingCosForm.bucket_alias.trim() || null,
        clear_secret_id: clearSecrets,
        clear_secret_key: clearSecrets,
        clear_session_token: clearSecrets,
        enabled: trainingCosForm.enabled,
        endpoint: trainingCosForm.endpoint.trim() || null,
        hosts: trainingCosForm.hosts.trim() || null,
        protocol: trainingCosForm.protocol.trim() || "http",
        region: trainingCosForm.region.trim() || null,
        secret_id: clearSecrets ? null : trainingCosForm.secret_id.trim() || null,
        secret_key: clearSecrets ? null : trainingCosForm.secret_key.trim() || null,
        session_token: clearSecrets ? null : trainingCosForm.session_token.trim() || null,
        target_prefix: trainingCosForm.target_prefix.trim() || "training/datasets"
      });
      setTrainingCosSettings(nextSettings);
      setTrainingCosForm(buildTrainingCosForm(nextSettings));
      setShowTrainingSecrets(false);
      toast.success(clearSecrets ? "训练 COS 密钥已清除。" : "训练 COS 配置已保存。");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存训练 COS 配置失败。");
    } finally {
      setTrainingPending(false);
    }
  }

  async function probeTrainingCosSettings() {
    setProbePending(true);
    try {
      const result = await probeSystemTrainingCosSettings();
      if (result.ok) {
        toast.success(result.message);
      } else {
        toast.error(result.message || "训练 COS 连通性测试失败。");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "训练 COS 连通性测试失败。");
    } finally {
      setProbePending(false);
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
            <h2 className="text-base font-semibold text-foreground">训练环境 COS</h2>
            <p className="text-sm leading-6 text-muted-foreground">
              用于把已上传的数据集同步到训练机器可访问的 COS。Secret 只保存在后端配置中，页面仅显示脱敏状态。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="rounded-full border border-border bg-background/60 px-3 py-1 text-xs text-muted-foreground">
              {trainingCosSettings.enabled ? "已启用" : "未启用"}
            </div>
            <div className="rounded-full border border-border bg-background/60 px-3 py-1 text-xs text-muted-foreground">
              {trainingCosSettings.has_secret_id && trainingCosSettings.has_secret_key
                ? "密钥已配置"
                : "密钥未配置"}
            </div>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="grid gap-5 lg:grid-cols-2">
            <label className="flex items-center gap-3 rounded-lg border border-border bg-muted/30 px-3 py-3 text-sm text-foreground lg:col-span-2">
              <input
                checked={trainingCosForm.enabled}
                className="h-4 w-4"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({
                    ...current,
                    enabled: event.target.checked
                  }))
                }
                type="checkbox"
              />
              启用训练环境 COS 同步
            </label>

            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="training-cos-protocol">
                Protocol
              </Label>
              <Input
                id="training-cos-protocol"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({ ...current, protocol: event.target.value }))
                }
                placeholder="http"
                value={trainingCosForm.protocol}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="training-cos-endpoint">
                Endpoint
              </Label>
              <Input
                id="training-cos-endpoint"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({ ...current, endpoint: event.target.value }))
                }
                placeholder="cos.ap-guangzhou.myqcloud.com"
                value={trainingCosForm.endpoint}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="training-cos-bucket">
                Bucket
              </Label>
              <Input
                id="training-cos-bucket"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({ ...current, bucket: event.target.value }))
                }
                placeholder="nta-1300272946"
                value={trainingCosForm.bucket}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="training-cos-alias">
                Alias
              </Label>
              <Input
                id="training-cos-alias"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({ ...current, bucket_alias: event.target.value }))
                }
                placeholder="nta"
                value={trainingCosForm.bucket_alias}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="training-cos-region">
                Region
              </Label>
              <Input
                id="training-cos-region"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({ ...current, region: event.target.value }))
                }
                placeholder="可留空，默认从 endpoint 推断"
                value={trainingCosForm.region}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="training-cos-prefix">
                Target Prefix
              </Label>
              <Input
                id="training-cos-prefix"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({
                    ...current,
                    target_prefix: event.target.value
                  }))
                }
                placeholder="training/datasets"
                value={trainingCosForm.target_prefix}
              />
            </div>
            <div className="space-y-2 lg:col-span-2">
              <Label className="text-foreground" htmlFor="training-cos-hosts">
                Hosts
              </Label>
              <Textarea
                className="min-h-24 font-mono text-xs"
                id="training-cos-hosts"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({
                    ...current,
                    hosts: event.target.value
                  }))
                }
                placeholder="21.0.81.61 nta-1300272946.cos.ap-guangzhou.myqcloud.com"
                value={trainingCosForm.hosts}
              />
              <div className="text-xs leading-5 text-muted-foreground">
                仅对训练 COS 请求做精确 host 覆盖；格式同 /etc/hosts，每行一个 IP 和域名。
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="training-cos-secret-id">
                SecretId
              </Label>
              <Input
                autoComplete="off"
                className="font-mono text-xs"
                id="training-cos-secret-id"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({ ...current, secret_id: event.target.value }))
                }
                placeholder={trainingCosSettings.secret_id_masked ?? "AKID..."}
                type={showTrainingSecrets ? "text" : "password"}
                value={trainingCosForm.secret_id}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="training-cos-secret-key">
                SecretKey
              </Label>
              <Input
                autoComplete="off"
                className="font-mono text-xs"
                id="training-cos-secret-key"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({ ...current, secret_key: event.target.value }))
                }
                placeholder={trainingCosSettings.secret_key_masked ?? "SecretKey"}
                type={showTrainingSecrets ? "text" : "password"}
                value={trainingCosForm.secret_key}
              />
            </div>
            <div className="space-y-2 lg:col-span-2">
              <Label className="text-foreground" htmlFor="training-cos-session-token">
                SessionToken
              </Label>
              <Input
                autoComplete="off"
                className="font-mono text-xs"
                id="training-cos-session-token"
                onChange={(event) =>
                  setTrainingCosForm((current) => ({
                    ...current,
                    session_token: event.target.value
                  }))
                }
                placeholder={trainingCosSettings.session_token_masked ?? "可选"}
                type={showTrainingSecrets ? "text" : "password"}
                value={trainingCosForm.session_token}
              />
            </div>
          </div>

          <aside className="space-y-3 rounded-lg border border-border bg-muted/30 p-4 text-sm">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <Cloud className="h-4 w-4" />
              当前配置
            </div>
            <ConfigLine label="Endpoint" value={trainingCosSettings.endpoint_url ?? "--"} />
            <ConfigLine label="Bucket" value={trainingCosSettings.bucket ?? "--"} />
            <ConfigLine label="Prefix" value={trainingCosSettings.target_prefix ?? "--"} />
            <ConfigLine label="Hosts" value={trainingCosSettings.hosts ?? "--"} />
            <ConfigLine label="SecretId" value={trainingCosSettings.secret_id_masked ?? "--"} />
            <ConfigLine label="SecretKey" value={trainingCosSettings.secret_key_masked ?? "--"} />
          </aside>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              disabled={trainingPending || probePending}
              onClick={() => setShowTrainingSecrets((current) => !current)}
              type="button"
              variant="outline"
            >
              {showTrainingSecrets ? <EyeOff className="mr-2 h-4 w-4" /> : <Eye className="mr-2 h-4 w-4" />}
              {showTrainingSecrets ? "隐藏密钥输入" : "显示密钥输入"}
            </Button>
            <Button
              disabled={
                trainingPending ||
                probePending ||
                (!trainingCosSettings.has_secret_id && !trainingCosSettings.has_secret_key)
              }
              onClick={() => void saveTrainingCosSettings(true)}
              type="button"
              variant="outline"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              清除密钥
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              disabled={trainingPending || probePending}
              onClick={() => void probeTrainingCosSettings()}
              type="button"
              variant="outline"
            >
              <PlugZap className="mr-2 h-4 w-4" />
              {probePending ? "测试中..." : "测试连通性"}
            </Button>
            <Button
              disabled={trainingPending || probePending}
              onClick={() => void saveTrainingCosSettings(false)}
              type="button"
            >
              <Save className="mr-2 h-4 w-4" />
              {trainingPending ? "保存中..." : "保存训练 COS"}
            </Button>
          </div>
        </div>
      </section>

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

function buildTrainingCosForm(settings: SystemTrainingCosSettings) {
  return {
    addressing_style: settings.addressing_style || "virtual",
    bucket: settings.bucket ?? "",
    bucket_alias: settings.bucket_alias ?? "",
    enabled: settings.enabled,
    endpoint: settings.endpoint ?? "",
    hosts: settings.hosts ?? "",
    protocol: settings.protocol || "http",
    region: settings.region ?? "",
    secret_id: "",
    secret_key: "",
    session_token: "",
    target_prefix: settings.target_prefix ?? "training/datasets"
  };
}

function ConfigLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1">
      <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">{label}</div>
      <div className="break-all font-mono text-xs text-foreground">{value}</div>
    </div>
  );
}
