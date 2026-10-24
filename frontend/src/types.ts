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
  changes?: Change[];
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
  story?: string | null;
}
export type Change =
  | { type: "flip_call" }
  | { type: "not_sent_off" }
  | { type: "shot_outcome"; outcome: "goal" | "saved" }
  | { type: "card"; card: "yellow" | "red" | null }
  | { type: "substitution"; team?: string; off?: string; on?: string }
  | { type: "tactics"; team: string; set: Record<string, number> };
export interface Club {
  code: string;
  name: string;
  squad: { id: string; name: string; pos: string; number: number }[];
}
export interface ForkRequest {
  match_id: string;
  event_id: string;
  change: Change;
}
export interface Probability {
  minute: number;
  min: string;
  home: number;
  draw: number;
  away: number;
}
export interface ForkResult {
  placeholder?: boolean;
  note?: string;
  match_id: string;
  event_id: string;
  change: Change;
  description: string;
  model_world: true;
  diverged: boolean;
  cached?: boolean;
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
  uncertainty: {
    shift_ci95: Record<"home" | "draw" | "away", [number, number]>;
  };
  history: {
    n: number;
    description: string;
    attacking_team: string;
    when_given: { n: number; win: number | null };
    when_not_given: { n: number; win: number | null };
    agrees_with_simulation: boolean | null;
  } | null;
  verdict?: string | null;
  score_spread: { score: Score; share: number }[];
}
