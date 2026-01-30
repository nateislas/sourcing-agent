export interface EvidenceSnippet {
    source_url: string;
    content: string;
    timestamp: string;
}

export interface Entity {
    canonical_name: string;
    aliases: string[];
    drug_class?: string;
    clinical_phase?: string;
    attributes: Record<string, string>;
    evidence: EvidenceSnippet[];
    mention_count: number;
    verification_status: "VERIFIED" | "UNVERIFIED" | "UNCERTAIN" | "REJECTED";
    rejection_reason?: string;
    confidence_score: number;
}

export interface WorkerState {
    id: string;
    research_id: string;
    strategy: string;
    queries: (string | Record<string, any>)[];
    page_budget: number;
    status: string;
    pages_fetched: number;
    entities_found: number;
    new_entities: number;
    personal_queue: string[];
    query_history?: Record<string, any>[];
    search_engine_history?: Record<string, any>[];
}

export interface Gap {
    description: string;
    priority: "low" | "medium" | "high";
    reasoning: string;
}

export interface ResearchPlan {
    current_hypothesis: string;
    findings_summary: string;
    gaps: Gap[];
    next_steps: string[];
    reasoning?: string;
}

export interface WorkerState {
    id: string;
    research_id: string;
    strategy: string;
    queries: (string | Record<string, any>)[];
    page_budget: number;
    status: string;
    pages_fetched: number;
    entities_found: number;
    new_entities: number;
    personal_queue: string[];
    query_history?: Record<string, any>[];
    search_engine_history?: Record<string, any>[];
}

export interface ResearchState {
    id: string;
    topic: string;
    status: "initialized" | "running" | "verification_pending" | "completed" | "failed";
    known_entities: Record<string, Entity>;
    visited_urls: string[];
    workers: Record<string, WorkerState>;
    plan: ResearchPlan;
    iteration_count: number;
    logs: string[];
}

export interface ResearchSessionSummary {
    session_id: string;
    topic: string;
    status: string;
    created_at: string;
    entities_count: number;
}
