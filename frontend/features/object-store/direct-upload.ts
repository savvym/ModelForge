"use client";

import COS from "cos-js-sdk-v5";
import type {
  ObjectStoreDirectUploadInitResponse,
  ObjectStoreUploadResponse
} from "@/types/api";

export type ObjectStoreDirectUploadProgressStatus = "preparing" | "uploading" | "finalizing";

export async function uploadFileWithObjectStoreDirectUpload(params: {
  file: File;
  initResponse: ObjectStoreDirectUploadInitResponse;
  onProgress: (payload: {
    status: ObjectStoreDirectUploadProgressStatus;
    uploadedBytes: number;
    totalBytes: number;
  }) => void;
}): Promise<ObjectStoreUploadResponse> {
  params.onProgress({
    status: "preparing",
    uploadedBytes: 0,
    totalBytes: params.file.size
  });

  if (params.initResponse.provider === "cos-sts") {
    await uploadBlobWithCosSts(params);
  } else {
    await uploadBlobWithPresignedUrl(params);
  }

  params.onProgress({
    status: "finalizing",
    uploadedBytes: params.file.size,
    totalBytes: params.file.size
  });

  return {
    bucket: params.initResponse.bucket,
    object_key: params.initResponse.object_key,
    uri: params.initResponse.uri,
    file_name: params.initResponse.file_name,
    size_bytes: params.file.size,
    content_type: params.initResponse.content_type ?? params.file.type ?? null,
    last_modified: new Date().toISOString()
  };
}

async function uploadBlobWithCosSts(params: {
  file: File;
  initResponse: ObjectStoreDirectUploadInitResponse;
  onProgress: (payload: {
    status: ObjectStoreDirectUploadProgressStatus;
    uploadedBytes: number;
    totalBytes: number;
  }) => void;
}) {
  const { initResponse } = params;
  if (!initResponse.region || !initResponse.sts) {
    throw new Error("COS STS 直传缺少必要的临时密钥或地域信息");
  }

  const sts = initResponse.sts;
  const cos = new COS({
    Domain: initResponse.domain ?? undefined,
    Protocol: initResponse.protocol ?? undefined,
    getAuthorization: (_, callback) => {
      callback({
        TmpSecretId: sts.tmp_secret_id,
        TmpSecretKey: sts.tmp_secret_key,
        SecurityToken: sts.session_token,
        StartTime: sts.start_time,
        ExpiredTime: sts.expired_time,
        ScopeLimit: sts.scope_limit
      });
    }
  });

  try {
    await cos.uploadFile({
      Bucket: initResponse.bucket,
      Region: initResponse.region,
      Key: initResponse.object_key,
      Body: params.file,
      SliceSize: 5 * 1024 * 1024,
      ContentType: initResponse.content_type ?? params.file.type ?? undefined,
      onProgress: (progress) => {
        params.onProgress({
          status: "uploading",
          uploadedBytes: Math.min(progress.total || params.file.size, progress.loaded),
          totalBytes: progress.total || params.file.size
        });
      }
    });
  } catch (error) {
    throw normalizeUploadError(error, "对象存储上传失败，请检查 COS STS 配置和网络连通性");
  }
}

async function uploadBlobWithPresignedUrl(params: {
  file: File;
  initResponse: ObjectStoreDirectUploadInitResponse;
  onProgress: (payload: {
    status: ObjectStoreDirectUploadProgressStatus;
    uploadedBytes: number;
    totalBytes: number;
  }) => void;
}) {
  const url = params.initResponse.url;
  if (!url) {
    throw new Error("对象存储直传缺少预签名地址");
  }

  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(params.initResponse.method ?? "PUT", url);

    for (const [key, value] of Object.entries(params.initResponse.headers ?? {})) {
      request.setRequestHeader(key, value);
    }

    request.upload.onprogress = (event) => {
      const totalBytes = event.lengthComputable ? event.total : params.file.size;
      params.onProgress({
        status: "uploading",
        uploadedBytes: event.loaded,
        totalBytes
      });
    };

    request.onerror = () => {
      reject(new Error("对象存储上传失败，请检查直传链路和对象存储配置"));
    };
    request.onabort = () => {
      reject(new Error("对象存储上传已中止"));
    };
    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(`对象存储上传失败: ${request.status} ${request.statusText}`));
        return;
      }

      params.onProgress({
        status: "uploading",
        uploadedBytes: params.file.size,
        totalBytes: params.file.size
      });
      resolve();
    };

    request.send(params.file);
  });
}

function normalizeUploadError(error: unknown, fallbackMessage: string) {
  if (error instanceof Error && error.message) {
    return error;
  }
  if (typeof error === "string" && error) {
    return new Error(error);
  }
  if (error && typeof error === "object") {
    const message =
      ("message" in error && typeof error.message === "string" && error.message) ||
      ("error" in error && typeof error.error === "string" && error.error) ||
      ("Code" in error && typeof error.Code === "string" && error.Code) ||
      ("code" in error && typeof error.code === "string" && error.code);
    if (message) {
      return new Error(message);
    }
  }
  return new Error(fallbackMessage);
}
