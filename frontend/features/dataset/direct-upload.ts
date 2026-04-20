"use client";

import {
  uploadFileWithObjectStoreDirectUpload,
  type ObjectStoreDirectUploadProgressStatus
} from "@/features/object-store/direct-upload";
import type { ObjectStoreDirectUploadInitResponse, ObjectStoreUploadResponse } from "@/types/api";

export type DatasetDirectUploadProgressStatus = ObjectStoreDirectUploadProgressStatus;

export async function uploadFileWithDirectUpload(params: {
  file: File;
  initResponse: ObjectStoreDirectUploadInitResponse;
  onProgress: (payload: {
    status: DatasetDirectUploadProgressStatus;
    uploadedBytes: number;
    totalBytes: number;
  }) => void;
}): Promise<ObjectStoreUploadResponse> {
  return uploadFileWithObjectStoreDirectUpload(params);
}
