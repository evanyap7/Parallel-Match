import type { Dispatch, SetStateAction } from "react";
import type { Change, Club, ForkResult, Match, MatchEvent } from "../types";

export interface TransportState {
  time: number;
  end: number;
  playing: boolean;
  speed: number;
  setTime: (t: number) => void;
  setPlaying: Dispatch<SetStateAction<boolean>>;
  setSpeed: (s: number) => void;
}

/** Everything a view needs; App owns the state, views only render it. */
export interface ViewProps {
  match: Match;
  clubs: Club[];
  moments: MatchEvent[];
  selected?: MatchEvent;
  selectedId: string;
  chooseMoment: (e: MatchEvent) => void;
  change?: Change;
  changeReady: boolean;
  canMock: boolean;
  updateChange: (c: Change) => void;
  explore: (fromText?: boolean) => void;
  cancel: () => void;
  loadExample: () => void;
  forkLoading: boolean;
  forkError: string;
  result?: ForkResult;
  forkEvents: MatchEvent[];
  attempt: number;
  whatIf: string;
  setWhatIf: (s: string) => void;
  focus: string;
  setFocus: (s: string) => void;
  side: "home" | "away";
  transport: TransportState;
  liveEngine: boolean;
}
