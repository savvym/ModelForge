export interface ProjectSummary {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  status: string;
  is_default: boolean;
  resource_count: number;
  member_count: number;
  dataset_count: number;
  evaluation_run_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends ProjectSummary {
  endpoint_count: number;
  model_provider_count: number;
  model_count: number;
}

export interface ProjectCreateInput {
  code: string;
  name: string;
  description?: string | null;
}

export interface DatasetSummary {
  id: string;
  name: string;
  description?: string | null;
  purpose?: string | null;
  format?: string | null;
  use_case?: string | null;
  modality?: string | null;
  recipe?: string | null;
  scope: string;
  source_type: string;
  status: string;
  latest_version?: number | null;
  latest_version_id?: string | null;
  owner_name?: string | null;
  tags: string[];
  record_count?: number | null;
  created_at: string;
  updated_at?: string | null;
}

export interface DatasetVersionSummary {
  id: string;
  dataset_id: string;
  version: number;
  status: string;
  description?: string | null;
  file_name?: string | null;
  format?: string | null;
  source_type: string;
  source_uri?: string | null;
  object_key?: string | null;
  record_count?: number | null;
  created_at: string;
  updated_at?: string | null;
  created_by?: string | null;
  file_count: number;
  files: DatasetFileSummary[];
}

export interface DatasetFileSummary {
  id: string;
  version_id: string;
  file_name: string;
  object_key: string;
  mime_type?: string | null;
  size_bytes?: number | null;
  etag?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface DatasetVersionPreview {
  dataset_id: string;
  version_id: string;
  file_id?: string | null;
  file_name: string;
  content: string;
  truncated: boolean;
  content_bytes: number;
}

export interface DatasetDetail extends DatasetSummary {
  source_uri?: string | null;
  versions: DatasetVersionSummary[];
}

export interface DatasetCreateInput {
  name: string;
  description?: string | null;
  purpose: string;
  format: string;
  use_case?: string | null;
  modality?: string | null;
  recipe?: string | null;
  scope: string;
  source_type: string;
  tags: string[];
  file_name?: string | null;
  source_uri?: string | null;
}

export interface DatasetCreateResponse {
  dataset_id: string;
  version_id: string;
  status: string;
  object_key?: string | null;
  source_uri?: string | null;
}

export interface DatasetDirectUploadInitInput {
  name: string;
  description?: string | null;
  purpose: string;
  format: string;
  use_case?: string | null;
  modality?: string | null;
  recipe?: string | null;
  scope: string;
  tags: string[];
  file_name: string;
  file_size: number;
  content_type?: string | null;
}

export interface DatasetVersionDirectUploadInitInput {
  description?: string | null;
  format?: string | null;
  file_name: string;
  file_size: number;
  content_type?: string | null;
}

export interface DatasetDirectUploadInitResponse extends DatasetCreateResponse {
  file_name: string;
  upload: ObjectStoreDirectUploadInitResponse;
}

export interface DatasetDirectUploadCompleteInput {
  upload: ObjectStoreUploadResponse;
}

export interface DatasetDirectUploadFailedInput {
  reason?: string | null;
}

export interface DatasetVersionCreateInput {
  description?: string | null;
  source_type: string;
  format?: string | null;
  file_name?: string | null;
  source_uri?: string | null;
}

export interface LakeBatchSummary {
  id: string;
  name: string;
  description?: string | null;
  stage: string;
  source_type: string;
  resource_type?: string | null;
  status: string;
  planned_file_count: number;
  completed_file_count: number;
  failed_file_count: number;
  total_size_bytes: number;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface LakeAssetSummary {
  id: string;
  batch_id: string;
  batch_name: string;
  parent_asset_id?: string | null;
  name: string;
  description?: string | null;
  stage: string;
  source_type: string;
  resource_type?: string | null;
  format?: string | null;
  mime_type?: string | null;
  relative_path?: string | null;
  object_key?: string | null;
  source_uri?: string | null;
  size_bytes?: number | null;
  record_count?: number | null;
  status: string;
  tags: string[];
  metadata: Record<string, unknown>;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LakeBatchCreateInput {
  name: string;
  description?: string | null;
  source_type?: string;
  resource_type?: string | null;
  planned_file_count: number;
  root_paths?: string[];
  tags?: string[];
  metadata?: Record<string, unknown>;
}

export interface LakeAssetDirectUploadInitInput {
  batch_id: string;
  description?: string | null;
  source_type?: string;
  resource_type?: string | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
  file_name: string;
  file_size: number;
  content_type?: string | null;
  relative_path?: string | null;
}

export interface LakeAssetDirectUploadInitResponse {
  batch_id: string;
  asset_id: string;
  status: string;
  object_key: string;
  source_uri: string;
  file_name: string;
  upload: ObjectStoreDirectUploadInitResponse;
}

export interface EvalJobSummary {
  id: string;
  name: string;
  description?: string | null;
  status: string;
  model_name: string;
  model_source: string;
  created_by?: string | null;
  progress_percent: number;
  progress_done?: number | null;
  progress_total?: number | null;
  inference_mode: string;
  eval_method: string;
  temporal_workflow_id?: string | null;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface EvalMetric {
  metric_name: string;
  metric_value: number;
  metric_unit?: string | null;
}

export interface EvalSampleAnalysis {
  sample_id: string;
  method: string;
  input_preview?: string | null;
  system_prompt?: string | null;
  rubric_source?: string | null;
  effective_rubric?: string | null;
  prediction_text?: string | null;
  reference_answers: string[];
  score?: number | null;
  raw_score?: number | null;
  passed: boolean;
  reason?: string | null;
  error?: string | null;
  latency_ms?: number | null;
  total_tokens?: number | null;
  judge_model_name?: string | null;
}

export interface EvalJobDetail extends EvalJobSummary {
  access_source: string;
  benchmark_name?: string | null;
  benchmark_version_id?: string | null;
  benchmark_version_name?: string | null;
  dataset_source_type: string;
  dataset_version_id?: string | null;
  dataset_name: string;
  dataset_source_uri?: string | null;
  artifact_prefix_uri?: string | null;
  source_object_uri?: string | null;
  results_prefix_uri?: string | null;
  samples_prefix_uri?: string | null;
  report_object_uri?: string | null;
  task_type: string;
  eval_mode: string;
  endpoint_name?: string | null;
  judge_model_name?: string | null;
  judge_prompt?: string | null;
  rubric?: string | null;
  batch_job_id?: string | null;
  metrics: EvalMetric[];
  sample_analysis: EvalSampleAnalysis[];
}

export interface EvalJobCreateInput {
  name: string;
  description?: string | null;
  benchmark_name?: string | null;
  benchmark_version_id?: string | null;
  benchmark_config?: Record<string, unknown> | null;
  model_id?: string | null;
  model_name: string;
  model_source: string;
  access_source: string;
  dataset_source_type: string;
  dataset_version_id?: string | null;
  dataset_name: string;
  dataset_source_uri?: string | null;
  inference_mode: string;
  task_type: string;
  eval_mode: string;
  eval_method: string;
  endpoint_name?: string | null;
  judge_model_id?: string | null;
  judge_model_name?: string | null;
  judge_prompt?: string | null;
  rubric?: string | null;
}

export interface BenchmarkVersionSummary {
  id: string;
  display_name: string;
  description: string;
  dataset_path?: string | null;
  dataset_source_uri?: string | null;
  sample_count: number;
  enabled: boolean;
  eval_job_count: number;
  latest_eval_at?: string | null;
}

export interface BenchmarkDefinitionSummary {
  name: string;
  display_name: string;
  family_name?: string | null;
  family_display_name?: string | null;
  description: string;
  default_eval_method: string;
  requires_judge_model: boolean;
  supports_custom_dataset: boolean;
  dataset_id?: string | null;
  category?: string | null;
  source_type?: string | null;
  paper_url?: string | null;
  tags: string[];
  metric_names: string[];
  subset_list: string[];
  eval_template_id?: string | null;
  eval_template_name?: string | null;
  eval_template_version?: number | null;
  eval_template_type?: string | null;
  eval_template_preset_id?: string | null;
  version_count: number;
  enabled_version_count: number;
  eval_job_count: number;
  latest_eval_at?: string | null;
  versions: BenchmarkVersionSummary[];
}

export interface BenchmarkDefinitionDetail extends BenchmarkDefinitionSummary {
  sample_schema_json: Record<string, unknown>;
  prompt_schema_json: Record<string, unknown>;
  prompt_config_json: Record<string, unknown>;
  field_mapping_json?: Record<string, unknown> | null;
  few_shot_num?: number | null;
  eval_split?: string | null;
  train_split?: string | null;
  prompt_template?: string | null;
  system_prompt?: string | null;
  few_shot_prompt_template?: string | null;
  sample_example_json?: Record<string, unknown> | null;
  statistics_json?: Record<string, unknown> | null;
  readme_json?: Record<string, unknown> | null;
  meta_updated_at?: string | null;
  meta_translation_updated_at?: string | null;
}

export interface BenchmarkDefinitionCreateInput {
  name?: string | null;
  display_name: string;
  description?: string | null;
  category?: string | null;
  tags?: string[];
  default_eval_method?: string;
  field_mapping?: Record<string, unknown> | null;
  prompt_template?: string | null;
  system_prompt?: string | null;
  requires_judge_model?: boolean;
  eval_template_id?: string | null;
}

export interface BenchmarkDefinitionUpdateInput {
  display_name?: string | null;
  description?: string | null;
  category?: string | null;
  tags?: string[];
  default_eval_method?: string;
  field_mapping?: Record<string, unknown> | null;
  prompt_template?: string | null;
  system_prompt?: string | null;
  requires_judge_model?: boolean;
  eval_template_id?: string | null;
}

export interface BenchmarkVersionCreateInput {
  id?: string | null;
  display_name: string;
  description?: string | null;
  dataset_source_uri?: string | null;
  enabled: boolean;
}

export interface BenchmarkVersionUpdateInput {
  display_name?: string | null;
  description?: string | null;
  dataset_source_uri?: string | null;
  enabled?: boolean | null;
}

// -- Eval Templates --

export interface EvalTemplateSummary {
  id: string;
  name: string;
  version: number;
  prompt: string;
  vars: string[];
  template_type: string;
  preset_id?: string | null;
  output_type: string;
  output_config: Record<string, unknown>;
  model?: string | null;
  provider?: string | null;
  model_params?: Record<string, unknown> | null;
  description?: string | null;
  created_at: string;
}

export interface EvalTemplateCreateInput {
  name: string;
  prompt: string;
  template_type?: string | null;
  preset_id?: string | null;
  output_type: string;
  output_config: Record<string, unknown>;
  model?: string | null;
  provider?: string | null;
  model_params?: Record<string, unknown> | null;
  description?: string | null;
}

export interface EvalTemplateUpdateInput {
  prompt?: string | null;
  template_type?: string | null;
  preset_id?: string | null;
  output_type?: string | null;
  output_config?: Record<string, unknown> | null;
  model?: string | null;
  provider?: string | null;
  model_params?: Record<string, unknown> | null;
  description?: string | null;
}

// -- Evaluation V2 --

export interface EvalSpecVersionSummaryV2 {
  id: string;
  version: string;
  display_name: string;
  description?: string | null;
  engine: string;
  execution_mode: string;
  engine_benchmark_name?: string | null;
  engine_config_json: Record<string, unknown>;
  scoring_config_json: Record<string, unknown>;
  dataset_source_uri?: string | null;
  template_spec_version_id?: string | null;
  default_judge_policy_id?: string | null;
  enabled: boolean;
  is_recommended: boolean;
  sample_count?: number | null;
  dataset_files: EvalSpecDatasetFileSummaryV2[];
}

export interface EvalSpecSummaryV2 {
  id: string;
  name: string;
  display_name: string;
  description?: string | null;
  capability_group?: string | null;
  capability_category?: string | null;
  status: string;
  tags_json: unknown[];
  input_schema_json: Record<string, unknown>;
  output_schema_json: Record<string, unknown>;
  versions: EvalSpecVersionSummaryV2[];
}

export interface EvalSpecDatasetFileSummaryV2 {
  id: string;
  file_key: string;
  display_name: string;
  role: string;
  position: number;
  file_name?: string | null;
  format?: string | null;
  source_uri?: string | null;
  object_key?: string | null;
  content_type?: string | null;
  size_bytes?: number | null;
  is_required: boolean;
  status: string;
  error_message?: string | null;
  last_synced_at?: string | null;
}

export interface EvalSuiteItemSummaryV2 {
  id: string;
  item_key: string;
  display_name: string;
  spec_version_id: string;
  position: number;
  weight: number;
  group_name?: string | null;
  enabled: boolean;
  overrides_json: Record<string, unknown>;
}

export interface EvalSuiteVersionSummaryV2 {
  id: string;
  version: string;
  display_name: string;
  description?: string | null;
  enabled: boolean;
  items: EvalSuiteItemSummaryV2[];
}

export interface EvalSuiteSummaryV2 {
  id: string;
  name: string;
  display_name: string;
  description?: string | null;
  capability_group?: string | null;
  status: string;
  versions: EvalSuiteVersionSummaryV2[];
}

export interface TemplateSpecVersionSummaryV2 {
  id: string;
  version: number;
  prompt: string;
  vars_json: string[];
  output_schema_json: Record<string, unknown>;
  parser_config_json: Record<string, unknown>;
  is_active: boolean;
}

export interface TemplateSpecSummaryV2 {
  id: string;
  name: string;
  display_name: string;
  description?: string | null;
  template_type: string;
  status: string;
  versions: TemplateSpecVersionSummaryV2[];
}

export interface JudgePolicySummaryV2 {
  id: string;
  name: string;
  display_name: string;
  description?: string | null;
  strategy: string;
  status: string;
  template_spec_version_id?: string | null;
  model_selector_json: Record<string, unknown>;
  execution_params_json: Record<string, unknown>;
  parser_config_json: Record<string, unknown>;
  retry_policy_json: Record<string, unknown>;
}

export interface EvaluationCatalogResponseV2 {
  specs: EvalSpecSummaryV2[];
  suites: EvalSuiteSummaryV2[];
  templates: TemplateSpecSummaryV2[];
  judge_policies: JudgePolicySummaryV2[];
}

export interface EvaluationTargetRefV2 {
  kind: "spec" | "suite";
  name: string;
  version: string;
  item_keys?: string[];
}

export interface EvaluationRunMetricV2 {
  metric_name: string;
  metric_value: number;
  metric_scope: string;
  metric_unit?: string | null;
  dimension_json: Record<string, unknown>;
  extra_json: Record<string, unknown>;
}

export interface EvaluationRunSampleV2 {
  sample_id: string;
  subset_name?: string | null;
  input_preview?: string | null;
  prediction_text?: string | null;
  reference_answers_json: string[];
  score?: number | null;
  raw_score?: number | null;
  passed: boolean;
  reason?: string | null;
  error?: string | null;
  latency_ms?: number | null;
  total_tokens?: number | null;
  metadata_json: Record<string, unknown>;
}

export interface EvaluationRunItemV2 {
  id: string;
  item_key: string;
  display_name: string;
  group_name?: string | null;
  weight: number;
  status: string;
  engine: string;
  execution_mode: string;
  report_uri?: string | null;
  raw_output_prefix_uri?: string | null;
  temporal_workflow_id?: string | null;
  progress_total?: number | null;
  progress_done?: number | null;
  error_code?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  metrics: EvaluationRunMetricV2[];
  samples: EvaluationRunSampleV2[];
}

export interface ModelBindingSnapshotV2 {
  model_id?: string | null;
  model_name: string;
  display_name: string;
  api_url: string;
  api_format: string;
  api_key?: string | null;
  organization?: string | null;
  headers: Record<string, string>;
  model_params: Record<string, unknown>;
}

export interface CompiledRunItemPlanV2 {
  item_key: string;
  display_name: string;
  group_name?: string | null;
  weight: number;
  engine: string;
  execution_mode: string;
  spec_id: string;
  spec_version_id: string;
  spec_name: string;
  spec_version: string;
  expected_sample_count?: number | null;
  engine_config: Record<string, unknown>;
  model_binding: ModelBindingSnapshotV2;
  judge_policy_snapshot?: Record<string, unknown> | null;
  template_snapshot?: Record<string, unknown> | null;
}

export interface CompiledRunPlanV2 {
  kind: "spec" | "suite";
  target_name: string;
  target_version: string;
  model_binding: ModelBindingSnapshotV2;
  judge_policy_snapshot?: Record<string, unknown> | null;
  items: CompiledRunItemPlanV2[];
  overrides: Record<string, unknown>;
}

export interface EvaluationRunSummaryV2 {
  id: string;
  name: string;
  description?: string | null;
  kind: string;
  status: string;
  model_name?: string | null;
  summary_report_uri?: string | null;
  temporal_workflow_id?: string | null;
  progress_total?: number | null;
  progress_done?: number | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface EvaluationRunDetailV2 extends EvaluationRunSummaryV2 {
  source_spec_id?: string | null;
  source_spec_version_id?: string | null;
  source_suite_id?: string | null;
  source_suite_version_id?: string | null;
  judge_policy_id?: string | null;
  execution_plan_json: CompiledRunPlanV2;
  metrics: EvaluationRunMetricV2[];
  items: EvaluationRunItemV2[];
}

export interface EvaluationRunCreateInputV2 {
  name?: string | null;
  description?: string | null;
  target: EvaluationTargetRefV2;
  model_id: string;
  judge_policy_id?: string | null;
  overrides?: Record<string, unknown>;
}

export interface EvaluationRunCancelResponseV2 {
  run_id: string;
  status: string;
}

export interface EvaluationLeaderboardRunCandidateV2 {
  run_id: string;
  run_name: string;
  model_name: string;
  score: number;
  metric_name: string;
  created_at: string;
  finished_at?: string | null;
}

export interface EvaluationLeaderboardEntryV2 extends EvaluationLeaderboardRunCandidateV2 {
  rank: number;
}

export interface EvaluationLeaderboardSummaryV2 {
  id: string;
  name: string;
  description?: string | null;
  target_kind: "spec" | "suite";
  target_name: string;
  target_display_name: string;
  target_version: string;
  target_version_display_name: string;
  score_metric_name: string;
  run_count: number;
  latest_run_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvaluationLeaderboardDetailV2 extends EvaluationLeaderboardSummaryV2 {
  entries: EvaluationLeaderboardEntryV2[];
}

export interface EvaluationLeaderboardCreateInputV2 {
  name: string;
  description?: string | null;
  target: EvaluationTargetRefV2;
  score_metric_name?: string;
  run_ids?: string[];
}

export interface EvaluationLeaderboardAddRunsInputV2 {
  run_ids: string[];
}

export interface EvalSpecVersionCreateInputV2 {
  version: string;
  display_name: string;
  description?: string | null;
  engine: string;
  execution_mode: string;
  engine_benchmark_name?: string | null;
  engine_config_json?: Record<string, unknown>;
  scoring_config_json?: Record<string, unknown>;
  dataset_source_uri?: string | null;
  template_spec_version_id?: string | null;
  default_judge_policy_id?: string | null;
  sample_count?: number | null;
  enabled?: boolean;
  is_recommended?: boolean;
  dataset_files?: EvalSpecDatasetFileCreateInputV2[];
}

export interface EvalSpecCreateInputV2 {
  name: string;
  display_name: string;
  description?: string | null;
  capability_group?: string | null;
  capability_category?: string | null;
  tags_json?: unknown[];
  input_schema_json?: Record<string, unknown>;
  output_schema_json?: Record<string, unknown>;
  initial_version: EvalSpecVersionCreateInputV2;
}

export interface EvalSpecVersionUpdateInputV2 {
  version_id: string;
  version: string;
  display_name: string;
  description?: string | null;
  engine: string;
  execution_mode: string;
  engine_benchmark_name?: string | null;
  engine_config_json?: Record<string, unknown>;
  scoring_config_json?: Record<string, unknown>;
  dataset_source_uri?: string | null;
  template_spec_version_id?: string | null;
  default_judge_policy_id?: string | null;
  sample_count?: number | null;
  enabled?: boolean;
  is_recommended?: boolean;
  dataset_files?: EvalSpecDatasetFileCreateInputV2[];
}

export interface EvalSpecDatasetFileCreateInputV2 {
  file_key: string;
  display_name: string;
  role?: string;
  position?: number;
  file_name?: string | null;
  format?: string | null;
  source_uri?: string | null;
  is_required?: boolean;
}

export interface EvalSpecUpdateInputV2 {
  display_name: string;
  description?: string | null;
  capability_group?: string | null;
  capability_category?: string | null;
  tags_json?: unknown[];
  input_schema_json?: Record<string, unknown>;
  output_schema_json?: Record<string, unknown>;
  version: EvalSpecVersionUpdateInputV2;
}

export interface EvalSuiteItemCreateInputV2 {
  item_key: string;
  display_name: string;
  spec_version_id: string;
  position?: number;
  weight?: number;
  group_name?: string | null;
  overrides_json?: Record<string, unknown>;
  enabled?: boolean;
}

export interface EvalSuiteVersionCreateInputV2 {
  version: string;
  display_name: string;
  description?: string | null;
  enabled?: boolean;
  items: EvalSuiteItemCreateInputV2[];
}

export interface EvalSuiteCreateInputV2 {
  name: string;
  display_name: string;
  description?: string | null;
  capability_group?: string | null;
  initial_version: EvalSuiteVersionCreateInputV2;
}

export interface EvalSuiteItemUpdateInputV2 {
  item_key: string;
  display_name: string;
  spec_version_id: string;
  position?: number;
  weight?: number;
  group_name?: string | null;
  overrides_json?: Record<string, unknown>;
  enabled?: boolean;
}

export interface EvalSuiteVersionUpdateInputV2 {
  version_id: string;
  version: string;
  display_name: string;
  description?: string | null;
  enabled?: boolean;
  items: EvalSuiteItemUpdateInputV2[];
}

export interface EvalSuiteUpdateInputV2 {
  display_name: string;
  description?: string | null;
  capability_group?: string | null;
  version: EvalSuiteVersionUpdateInputV2;
}

export interface TemplateSpecCreateInputV2 {
  name: string;
  display_name: string;
  description?: string | null;
  template_type: string;
  prompt: string;
  vars_json?: string[];
  output_schema_json?: Record<string, unknown>;
  parser_config_json?: Record<string, unknown>;
}

export interface JudgePolicyCreateInputV2 {
  name: string;
  display_name: string;
  description?: string | null;
  strategy: string;
  template_spec_version_id?: string | null;
  model_selector_json?: Record<string, unknown>;
  execution_params_json?: Record<string, unknown>;
  parser_config_json?: Record<string, unknown>;
  retry_policy_json?: Record<string, unknown>;
}

export interface WorkflowLaunchResponse {
  job_id: string;
  workflow_id: string;
  status: string;
  stream_url: string;
}

export interface ModelProviderSummary {
  id: string;
  name: string;
  provider_type: string;
  adapter: string;
  api_format: string;
  base_url: string;
  organization?: string | null;
  description?: string | null;
  status: string;
  has_api_key: boolean;
  model_count: number;
  last_synced_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModelProviderCreateInput {
  name: string;
  provider_type: string;
  adapter: string;
  api_format: string;
  base_url: string;
  api_key?: string | null;
  organization?: string | null;
  description?: string | null;
}

export interface ModelProviderUpdateInput {
  name?: string;
  api_format?: string;
  base_url?: string;
  api_key?: string | null;
  organization?: string | null;
  status?: string;
  description?: string | null;
}

export interface ModelProviderSyncResult {
  provider_id: string;
  provider_name: string;
  synced_count: number;
  created_count: number;
  updated_count: number;
  last_synced_at: string;
}

export interface RegistryModelSummary {
  id: string;
  name: string;
  model_code?: string | null;
  vendor?: string | null;
  source?: string | null;
  api_format?: string | null;
  category?: string | null;
  description?: string | null;
  status: string;
  provider_id?: string | null;
  provider_name?: string | null;
  is_provider_managed: boolean;
  last_synced_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RegistryModelCreateInput {
  name: string;
  model_code: string;
  provider_id?: string | null;
  vendor?: string | null;
  source: string;
  api_format: string;
  category?: string | null;
  description?: string | null;
}

export interface RegistryModelUpdateInput {
  name?: string;
  model_code?: string;
  provider_id?: string | null;
  vendor?: string | null;
  api_format?: string;
  category?: string | null;
  status?: string;
  description?: string | null;
}

export interface RegistryModelTestInput {
  prompt: string;
}

export interface RegistryModelTestResponse {
  model_id: string;
  model_name: string;
  model_code: string;
  provider_id: string;
  provider_name: string;
  api_format: string;
  prompt: string;
  output_text: string;
  latency_ms: number;
  request_id?: string | null;
}

export interface RegistryModelChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface RegistryModelChatInput {
  messages: RegistryModelChatMessage[];
  reasoning_depth?: string | null;
}

export interface RegistryModelChatResponse {
  model_id: string;
  model_name: string;
  model_code: string;
  provider_id: string;
  provider_name: string;
  api_format: string;
  output_text: string;
  reasoning_text?: string | null;
  latency_ms: number;
  request_id?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
}

export interface ObjectStorePrefixEntry {
  name: string;
  prefix: string;
}

export interface ObjectStoreObjectEntry {
  key: string;
  name: string;
  size_bytes: number;
  last_modified?: string | null;
}

export interface ObjectStoreBrowserResponse {
  bucket: string;
  prefix: string;
  parent_prefix?: string | null;
  search_query?: string | null;
  buckets: string[];
  prefixes: ObjectStorePrefixEntry[];
  objects: ObjectStoreObjectEntry[];
}

export interface ObjectStoreUploadResponse {
  bucket: string;
  object_key: string;
  uri: string;
  file_name: string;
  size_bytes: number;
  content_type?: string | null;
  last_modified: string;
}

export interface ObjectStoreObjectPreviewResponse {
  bucket: string;
  object_key: string;
  file_name: string;
  preview_kind: "text" | "image" | "pdf" | "unsupported";
  content_type?: string | null;
  content?: string | null;
  truncated: boolean;
  content_bytes?: number | null;
}

export interface ObjectStoreFolderCreateResponse {
  bucket: string;
  prefix: string;
  name: string;
  uri: string;
}

export interface ObjectStoreDirectUploadInitResponse {
  bucket: string;
  object_key: string;
  uri: string;
  file_name: string;
  size_bytes: number;
  content_type?: string | null;
  expires_in: number;
  method: string;
  headers: Record<string, string>;
  url: string;
}

export interface EvalJobStatusEvent {
  job_type: string;
  job_id: string;
  status: string;
  phase: string;
  step: number;
  total_steps: number;
  timestamp: string;
  started_at?: string | null;
  finished_at?: string | null;
  batch_job_id?: string | null;
  error_message?: string | null;
  metrics?: EvalMetric[];
}

export interface EvalLogEvent {
  job_type: string;
  job_id: string;
  level: string;
  message: string;
  timestamp: string;
}
