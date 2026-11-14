// Mirrors backend/src/interview_api/schemas.py

export type User = { id: string; email: string; name: string; created_at: string };

export type Meta = {
  roles: string[];
  levels: string[];
  min_questions: number;
  max_questions: number;
  default_questions: number;
  max_answer_seconds: number;
  max_audio_bytes: number;
  ai_mode: "gemini" | "demo";
  ai_model: string;
  transcriber: string;
};

export type Feedback = {
  summary: string;
  strengths: string[];
  improvements: string[];
  clarity_feedback: string;
  clarity_notes: string[];
};

export type Answer = {
  id: string;
  created_at: string;
  transcript: string;
  transcriber: string;
  audio_seconds: number;
  audio_kept: boolean;
  speaking_seconds: number;
  word_count: number;
  wpm: number;
  filler_count: number;
  fillers: Record<string, number>;
  long_pause_count: number;
  longest_pause_s: number;
  relevance: number;
  correctness: number;
  depth: number;
  structure: number;
  clarity_llm: number;
  content_score: number;
  clarity_computed: number;
  clarity_score: number;
  overall_score: number;
  feedback: Feedback;
  example_answer: string;
  ai_model: string;
};

export type Question = {
  id: string;
  position: number;
  kind: "behavioural" | "technical";
  skill: string;
  text: string;
  guidance: string | null;
  answer: Answer | null;
};

export type InterviewSummary = {
  id: string;
  role: string;
  level: string;
  status: "in_progress" | "completed";
  created_at: string;
  completed_at: string | null;
  overall_score: number | null;
  content_score: number | null;
  clarity_score: number | null;
  question_count: number;
  answered_count: number;
};

export type Interview = InterviewSummary & {
  ai_model: string;
  summary: {
    summary: string;
    strengths: string[];
    priorities: string[];
    skipped_questions: number;
  } | null;
  questions: Question[];
};

export type ProgressPoint = {
  interview_id: string;
  completed_at: string;
  role: string;
  level: string;
  overall: number | null;
  content: number | null;
  clarity: number | null;
  relevance: number | null;
  correctness: number | null;
  depth: number | null;
  structure: number | null;
  behavioural: number | null;
  technical: number | null;
  wpm: number | null;
  fillers_per_100: number | null;
};

export type SkillStat = {
  skill: string;
  first: number | null;
  latest: number | null;
  average: number | null;
  change: number | null;
};

export type RoleStat = {
  role: string;
  interviews: number;
  average_overall: number | null;
  best_overall: number | null;
  latest_overall: number | null;
};

export type Progress = {
  role: string | null;
  roles_practised: string[];
  points: ProgressPoint[];
  skills: SkillStat[];
  by_role: RoleStat[];
  question_skills: { skill: string; answers: number; average_overall: number | null }[];
};
