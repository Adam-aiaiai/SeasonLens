import type {
  ActionProposal,
  ApprovalDecision,
  EvidenceReference,
  Projection,
} from "./contracts";

export interface ExtensionPanel {
  id: string;
  title: string;
  projectionType: string;
  placement: "primary" | "secondary" | "drawer" | "timeline";
}

export interface ExtensionDefinition {
  id: string;
  name: string;
  routes: string[];
  panels: ExtensionPanel[];
  renderProjection(projection: Projection): unknown;
  renderProposal(proposal: ActionProposal): unknown;
  renderEvidence(reference: EvidenceReference): unknown;
  submitApproval(decision: ApprovalDecision): Promise<void>;
}

export interface StudyCondition {
  id: string;
  extensionId: string;
  projectionSet: string[];
  enabledCapabilities: string[];
  agentMode: "live-llm" | "rule-policy" | "replay" | "human-authored";
}
