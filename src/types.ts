export interface GigSearchRecord {
  niche: string;
  global_position?: number;
  organic_position?: number;
  sponsored_position?: number;
  page_number?: number;
  page_position?: number;
  is_sponsored?: boolean;
  card_title?: string;
  card_price?: string;
  badges?: string[];
  seller_online?: boolean;
}

export interface GigPackage {
  name: string;
  price_usd: number;
  description: string;
  delivery_days: number;
  revisions: string | number;
  deliverables?: string[];
  features?: Record<string, boolean | string | number>;
  ideal_for?: string;
}

export interface GigFAQ {
  question: string;
  answer: string;
}

export interface GigReview {
  rating?: number;
  comment?: string;
  buyer_name?: string;
  buyer_country?: string;
  created_at?: string;
  work_sample?: boolean;
  seller_response?: string;
}

export interface GigResult {
  url: string;
  title: string;
  search?: GigSearchRecord;
  seller_name?: string;
  seller_username?: string;
  seller_level?: string;
  seller_country?: string;
  member_since?: string;
  average_response_time?: string;
  last_delivery?: string;
  rating?: number;
  review_count?: number;
  starting_price_usd?: number;
  hourly_rate_usd?: number;
  currency?: string;
  category_path?: string[];
  gallery_count?: number;
  has_video?: boolean;
  fetched_at?: string;
  error?: string;
  meta_description?: string;
  about_text?: string;
  packages?: GigPackage[];
  packages_text?: string;
  faqs?: GigFAQ[];
  faq_text?: string;
  review_summary?: string;
  visible_reviews?: GigReview[];
  reviews_text?: string;
  related_tags?: string[];
  media_urls?: string[];
  json_ld?: any;
  raw_visible_text?: string;
}

export interface JobRecord {
  id: string;
  niche: string;
  limit: number;
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "interrupted";
  stage?: string;
  progress_percent?: number;
  pages_scanned?: number;
  available_results?: number;
  discovered_count?: number;
  processed_count?: number;
  success_count?: number;
  failed_count?: number;
  discovery_source?: string;
  started_at?: string;
  finished_at?: string;
  error?: string;
  warnings?: string[];
  downloads?: {
    json?: string;
    csv?: string;
  };
}

export interface AIRunRecord {
  id: string;
  job_id: string;
  mode: "dry_run" | "test" | "standard" | "deep";
  status: "queued" | "running" | "completed" | "failed" | "interrupted";
  stage?: string;
  progress_percent?: number;
  selected_gigs?: number;
  processed_gigs?: number;
  total_tokens?: number;
  actual_cost_usd?: number;
  estimated_cost_usd?: number;
  llm_used?: boolean;
  started_at?: string;
  finished_at?: string;
  error?: string;
  result_url?: string;
}

export interface GenerationRunRecord {
  id: string;
  job_id: string;
  mode: "dry_run" | "test" | "standard" | "deep";
  status: "queued" | "running" | "completed" | "failed" | "interrupted";
  stage?: string;
  progress_percent?: number;
  approval_status?: "draft" | "approved" | "rejected";
  total_tokens?: number;
  actual_cost_usd?: number;
  estimated_cost_usd?: number;
  llm_used?: boolean;
  started_at?: string;
  finished_at?: string;
  error?: string;
  result_url?: string;
  markdown_url?: string;
}

export interface SimpleWorkflowRecord {
  id: string;
  niche: string;
  quality: "fast" | "recommended" | "best";
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "interrupted";
  stage?: "research" | "understand" | "build" | "ready";
  message?: string;
  progress_percent?: number;
  job_id?: string;
  ai_run_id?: string;
  generation_run_id?: string;
  inputs?: Record<string, any>;
  warnings?: string[];
  error?: string;
  markdown_url?: string;
  started_at?: string;
  finished_at?: string;
}
