import type { Projection } from "./contracts";

export type SeasonLensStage = "OBSERVE" | "INITIAL_COMMITTED" | "POSITIVE_FEEDBACK" | "HINT" | "REOBSERVE" | "REVISED_COMMITTED" | "REVEAL" | "REFLECTION" | "COMPLETE";
export type SeasonLensStudyMode = "training" | "unaided_test" | "transfer";
export type SeasonLensCondition = "answer-first" | "observation-first-yoked" | "observation-first-contingent";

export interface NormalizedRectangle { x: number; y: number; width: number; height: number; }

export interface SeasonLensAttempt {
  item_id: string;
  selected_region: NormalizedRectangle;
  observation_text: string;
  interpretation_text: string;
  selected_stage_id: string;
  confidence?: number;
  timestamp?: string;
  revision_submitted_at?: string;
}

export interface SeasonLensItemView {
  item_id: string;
  plant_name: string;
  image_path: string;
  prompts: { observation: string; interpretation: string; };
  stage_options: Array<{ id: string; label: string }>;
  region_selection_kind: "explicit-rectangle-proxy";
}

export interface SeasonLensProjectionData {
  session_id: string;
  participant_id: string;
  condition: SeasonLensCondition;
  study_mode: SeasonLensStudyMode;
  stage: SeasonLensStage;
  item: SeasonLensItemView;
  initial_attempt: SeasonLensAttempt | null;
  revised_attempt: SeasonLensAttempt | null;
  has_next_item: boolean;
  hint: { hint_id: string; hint_level: number; hint_text: string; hint_shown_at: string; } | null;
  positive_feedback: { text: string; shown_at: string; } | null;
  hint_received: boolean;
  expert_reveal?: {
    relevant_region: string;
    diagnostic_cue: string;
    interpretation: string;
    target_region: { x: number; y: number; width: number; height: number };
  };
  reflection: { reflection_text: string; reflection_category: string | null; reflection_submitted_at: string; } | null;
}

// Researcher-only; never part of SeasonLensProjectionData.
export interface SeasonLensDiagnostic {
  region_correct: boolean;
  selected_semantic_region: string;
  selected_region_label: string;
  target_region_id: string;
  target_iou: number;
  best_distractor_iou: number;
  cue_correct: boolean;
  interpretation_correct: boolean;
  primary_error: "REGION_MISS" | "CUE_MISIDENTIFIED" | "INTERPRETATION_ERROR" | "CORRECT";
  region_iou: number;
}

// Authored study metadata, available only on the researcher API.
export interface SeasonLensSemanticRegion {
  id: string;
  label: string;
  rect: NormalizedRectangle;
}

export type SeasonLensProjection = Projection<SeasonLensProjectionData>;
