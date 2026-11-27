export type Choice = 'YES' | 'NO' | 'ABSTAIN';
export type RuleKind = 'SIMPLE' | 'SPECIAL' | 'ELECTION';
export type VotingMode = 'NOMINAL' | 'SECRET';
export type AssemblyState = 'DRAFT' | 'PUBLISHED' | 'INSTALLED' | 'CLOSED';

export interface DemoAccount {
  id: string;
  name: string;
  email: string;
  organization: string;
}

export interface Config {
  demo: boolean;
  authenticated: boolean;
  demo_password_required: boolean;
  official_ready: boolean;
  oidc_configured: boolean;
  institution_name: string;
  institutional_domain: string;
  demo_accounts: DemoAccount[];
}

export interface Me {
  id: string;
  name: string;
  email: string;
  mb: string;
  organization: string;
  is_admin: boolean;
  authentication_kind: string;
}

export interface AssemblySummary {
  id: string;
  title: string;
  code: string;
  state: AssemblyState;
  is_demo: boolean;
}

export interface Option {
  id: string;
  label: string;
}

export interface AgendaItem {
  id: string;
  position: number;
  title: string;
  body: string;
  rule: RuleKind;
  voting_mode: VotingMode;
  options: Option[];
  voted: boolean;
}

export interface Receipt {
  choice: string | null;
  protocol: string;
  executor: string;
}

export interface BallotCard {
  owner_id: string;
  name: string;
  own: boolean;
  available: boolean;
  receipt: Receipt | null;
}

export interface SimpleResult {
  yes: number;
  no: number;
  abstain: number;
  outcome: 'APPROVED' | 'NOT_APPROVED';
}

export interface ElectionResult {
  options: (Option & { votes: number })[];
  blank: number;
  valid: number;
  outcome: 'ELECTED' | 'TIE' | 'NO_VALID_VOTES';
  winner: (Option & { votes: number }) | null;
}

export type RoundResult = (SimpleResult | ElectionResult) & {
  not_voted: number;
  authorized_during_window: number;
  voting_mode: VotingMode;
  kind: RuleKind;
};

export interface VoteRow {
  owner_name: string;
  executor_name: string;
  choice?: Choice;
  protocol: string;
}

export interface RoundState {
  id: string;
  title: string;
  body: string;
  hash: string;
  state: 'OPEN' | 'CLOSED';
  closes_at: string;
  kind: RuleKind;
  voting_mode: VotingMode;
  options: Option[];
  received: number;
  cards: BallotCard[];
  result: RoundResult | null;
  nominal_votes: VoteRow[];
  participants: VoteRow[];
}

export interface ProxyRow {
  id: string;
  grantor_id: string;
  representative_id: string;
  grantor: string;
  representative: string;
  condition: string;
  status: string;
}

export interface FloorRow {
  id: string;
  member_id: string;
  name: string;
  kind: 'NORMAL' | 'ORDER';
  state: 'WAITING' | 'GRANTED';
}

export interface AssemblyData {
  id: string;
  code: string;
  title: string;
  organization: string;
  state: AssemblyState;
  president: string;
  secretary: string;
  installation: { call?: number; present?: number };
  quorum: { eligible: number; present: number; required: number; represented: number };
  presence: { present: boolean; session_id: string | null };
  agenda: AgendaItem[];
  proxies: ProxyRow[];
  round: RoundState | null;
  floor: FloorRow[];
  members: { id: string; name: string; mb: string }[];
  next_demo_id: string | null;
}

export interface InboxMessage {
  id: string;
  subject: string;
  code: string;
}

export interface MemberRow {
  id: string;
  name: string;
  email: string;
  number: string;
  can_vote: boolean;
  can_speak: boolean;
  is_admin: boolean;
  simulation: boolean;
  identity_linked: boolean;
}

export interface Organization {
  id: string;
  name: string;
  email_domain: string;
  members: MemberRow[];
  assemblies: { id: string; code: string; title: string; state: AssemblyState }[];
}

export interface DraftDetail {
  id: string;
  code: string;
  title: string;
  state: AssemblyState;
  first_call_at: string;
  second_call_at: string;
  president: { id: string; name: string };
  secretary: { id: string; name: string };
  agenda: {
    id: string;
    position: number;
    title: string;
    body: string;
    rule: RuleKind;
    voting_mode: VotingMode;
    options: string[];
  }[];
}

export interface ImportError {
  line: number;
  error: string;
}
