export type ActorType = "human" | "agent" | "system" | "tool";

export interface Actor {
  actorType: ActorType;
  actorId: string;
}

export interface ActionProposal<TPayload = Record<string, unknown>> {
  proposalId: string;
  extensionId: string;
  actionType: string;
  actor: Actor;
  payload: TPayload;
  evidenceRefs: string[];
  expectedStateVersion: number;
  requiresConfirmation: boolean;
  rationale?: string;
}

export interface EvidenceReference {
  id: string;
  label: string;
  kind: string;
  status: "available" | "missing" | "stale" | "unbound";
  sourceEventIds: string[];
}

export interface Projection<TData = unknown> {
  extensionId: string;
  aggregateId: string;
  stateVersion: number;
  projectionType: string;
  data: TData;
}

export interface ApprovalDecision {
  proposalId: string;
  approved: boolean;
  rationale?: string;
}
