"use client";

import type { ObjectStoreDirectUploadInitResponse, ObjectStoreUploadResponse } from "@/types/api";

export type DatasetDirectUploadProgressStatus = "preparing" | "uploading" | "finalizing";

export async function uploadFileWithDirectUpload(params: {
  file: File;
  initResponse: ObjectStoreDirectUploadInitResponse;
  onProgress: (payload: {
    status: DatasetDirectUploadProgressStatus;
    uploadedBytes: number;
    totalBytes: number;
  }) => void;
}): Promise<ObjectStoreUploadResponse> {
  params.onProgress({
    status: "preparing",
    uploadedBytes: 0,
    totalBytes: params.file.size
  });

  await uploadBlobWithProgress({
    body: params.file,
    headers: params.initResponse.headers,
    onProgress: (uploadedBytes, totalBytes) =>
      params.onProgress({
        status: "uploading",
        uploadedBytes,
        totalBytes
      }),
    url: params.initResponse.url
  });

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

function uploadBlobWithProgress(params: {
  url: string;
  body: Blob;
  headers?: Record<string, string>;
  onProgress?: (uploadedBytes: number, totalBytes: number) => void;
}) {
  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", params.url);

    for (const [key, value] of Object.entries(params.headers ?? {})) {
      request.setRequestHeader(key, value);
    }

    request.upload.onprogress = (event) => {
      if (!params.onProgress) {
        return;
      }

      const totalBytes = event.lengthComputable ? event.total : params.body.size;
      params.onProgress(event.loaded, totalBytes);
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

      params.onProgress?.(params.body.size, params.body.size);
      resolve();
    };

    request.send(params.body);
  });
}
