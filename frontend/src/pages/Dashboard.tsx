import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getSessionState, getExportUrl } from '../services/api';
import type { ResearchState } from '../types';
import { StatusBanner } from '../components/StatusBanner';
import { LogStream } from '../components/LogStream';
import { WorkersGrid } from '../components/WorkersGrid';
import { ResultsTable } from '../components/ResultsTable';
import { PlanOverview } from '../components/PlanOverview';
import { ArrowLeft, Loader2, Download } from 'lucide-react';
import { ResearchTimeline } from '../components/ResearchTimeline';
import { DiscoveryStats } from '../components/DiscoveryStats';

export const Dashboard: React.FC = () => {
    const { sessionId } = useParams<{ sessionId: string }>();
    const [state, setState] = useState<ResearchState | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        if (!sessionId) return;
        try {
            const data = await getSessionState(sessionId);
            // Deep equal check to prevent unnecessary re-renders
            if (JSON.stringify(data) !== JSON.stringify(state)) {
                setState(data);
            }
        } catch (err) {
            console.error(err);
            // Don't set error on polling failure if we already have data
            if (!state) setError("Failed to load session");
        } finally {
            setLoading(false);
        }
    }, [sessionId, state]);

    // Initial load
    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Polling
    useEffect(() => {
        if (!state || ['completed', 'failed'].includes(state.status)) return;

        const interval = setInterval(fetchData, 3000); // Poll every 3s
        return () => clearInterval(interval);
    }, [fetchData, state?.status]);

    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
        );
    }

    if (error || !state) {
        return (
            <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-4">
                <div className="text-red-500 font-medium">{error || "Session not found"}</div>
                <Link to="/" className="text-primary hover:underline">Return Home</Link>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background flex flex-col">
            <div className="p-6">
                <div className="max-w-7xl mx-auto space-y-6">

                    {/* Header */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <Link to="/" className="p-2 hover:bg-muted rounded-lg transition-colors text-muted-foreground hover:text-foreground">
                                <ArrowLeft className="w-5 h-5" />
                            </Link>
                            <span className="text-sm font-medium text-muted-foreground truncate">
                                Research Session / {state.id}
                            </span>
                        </div>
                        <div className="text-[10px] font-mono text-muted-foreground bg-muted/30 px-3 py-1 rounded-full border">
                            ITERATION {state.iteration_count}
                        </div>
                    </div>

                    <StatusBanner status={state.status} topic={state.topic} />

                    {/* Progress Analytics */}
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                        <div className="lg:col-span-5">
                            <ResearchTimeline status={state.status} iteration={state.iteration_count} />
                        </div>
                        <div className="lg:col-span-7">
                            <DiscoveryStats workers={state.workers} />
                        </div>
                    </div>

                    {/* Research Plan Overview */}
                    {state.plan && <PlanOverview plan={state.plan} entities={state.known_entities} />}

                    {/* Main Grid */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div className="lg:col-span-2">
                            <LogStream logs={state.logs} />
                        </div>
                        <div className="lg:max-h-[600px] overflow-y-auto pr-2 custom-scrollbar overscroll-contain">
                            <WorkersGrid workers={state.workers} />
                        </div>
                    </div>

                    {/* Results Section */}
                    <div className="space-y-4 pb-12">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xl font-bold text-foreground">Discovered Assets</h2>
                            <a
                                href={getExportUrl(state.id)}
                                download
                                className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary hover:bg-primary/20 rounded-xl transition-all text-sm font-semibold border border-primary/20"
                            >
                                <Download className="w-4 h-4" />
                                Export CSV
                            </a>
                        </div>
                        <ResultsTable entities={state.known_entities} />
                    </div>
                </div>
            </div>
        </div>
    );
};
