export type Score = [number, number];
export interface MatchEvent {
  id: string;
  step: number;
  t: number;
  min: string;
  period: number;
  type: string;
  team?: string;
  player?: string;
  xy?: [number, number];
  score: Score;
  contestable?: boolean;
  call?: string;
  law?: string;
  margin?: number;
  contact?: number;
  offside_margin?: number;
  success?: boolean;
  kind?: string;
  outcome?: string;
  xg?: number;
  off?: string;
  color?: string;
  to?: string;
}
export interface Match {
  match_id: string;
  seed?: number;
  home: string;
  away: string;
  score: Score;
  events: MatchEvent[];
}
export interface MatchSummary {
  match_id: string;
  home?: string;
  away?: string;
}
export interface Change {
  type: "flip_call";
  call: string;
}
export interface ForkRequest {
  match_id: string;
  event_id: string;
  change: Change;
}
export interface Probability {
  min: number;
  home: number;
  draw: number;
  away: number;
}
export interface ForkResult {
  placeholder?: boolean;
  note?: string;
  request: ForkRequest;
  divergence: { event_id: string; step: number; t: number; min: string };
  moment: Partial<MatchEvent>;
  original: { final_score: Score; win_prob: Probability[] };
  alternate: {
    final_score: Score;
    win_prob: Probability[];
    timeline: MatchEvent[];
    timeline_note?: string;
  };
  rollouts: number;
  outcome_shift: { home: number; draw: number; away: number };
  uncertainty: { home_win_ci95: [number, number] };
  history: {
    n: number;
    description: string;
    home_win_share: number;
    agrees_with_simulation: boolean | null;
  };
  verdict: string;
}
