import React, { useEffect } from 'react';
import type { WorkerState } from '../types';
import { X, Bot, History, ListOrdered, Search, Globe, ChevronRight } from 'lucide-react';

interface Props {
    worker: WorkerState | null;
    isOpen: boolean;
    onClose: () => void;
}

export const WorkerDetailModal: React.FC<Props> = ({ worker, isOpen, onClose }) => {
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => { document.body.style.overflow = 'unset'; };
    }, [isOpen]);

    if (!isOpen || !worker) return null;

    const queryHistory = worker.query_history || [];
    const searchHistory = worker.search_engine_history || [];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
            <div
                className="absolute inset-0 bg-background/80 backdrop-blur-sm transition-opacity animate-in fade-in duration-300"
                onClick={onClose}
            />

            <div className="relative w-full max-w-2xl max-h-[85vh] bg-card border rounded-3xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-300">

                {/* Header */}
                <div className="p-6 border-b bg-muted/30">
                    <div className="flex items-start justify-between">
                        <div className="flex items-center gap-4">
                            <div className="p-3 bg-primary/10 rounded-2xl text-primary">
                                <Bot className="w-8 h-8" />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-foreground leading-tight">
                                    {worker.strategy.replace(/_/g, ' ')}
                                </h2>
                                <p className="text-sm text-muted-foreground font-mono">
                                    {worker.id}
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-muted rounded-xl transition-colors text-muted-foreground hover:text-foreground"
                        >
                            <X className="w-6 h-6" />
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto overscroll-contain">
                    <div className="p-6 space-y-8">

                        {/* Status Summary */}
                        <div className="grid grid-cols-3 gap-4">
                            <div className="bg-muted/50 p-4 rounded-2xl border text-center">
                                <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">Status</div>
                                <div className={`text-xs font-bold ${worker.status === 'ACTIVE' ? 'text-green-500' : 'text-muted-foreground'}`}>
                                    {worker.status}
                                </div>
                            </div>
                            <div className="bg-muted/50 p-4 rounded-2xl border text-center">
                                <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">Efficiency</div>
                                <div className="text-xs font-bold text-foreground">
                                    {worker.pages_fetched > 0
                                        ? ((worker.entities_found / worker.pages_fetched).toFixed(2))
                                        : '0.00'} E/P
                                </div>
                            </div>
                            <div className="bg-muted/50 p-4 rounded-2xl border text-center">
                                <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">Coverage</div>
                                <div className="text-xs font-bold text-foreground">
                                    {Math.round((worker.pages_fetched / worker.page_budget) * 100)}%
                                </div>
                            </div>
                        </div>

                        {/* Current Active Query */}
                        <div className="space-y-4">
                            <h3 className="text-sm font-semibold flex items-center gap-2 text-primary">
                                <Search className="w-4 h-4" />
                                Active Objective
                            </h3>
                            <div className="bg-primary/5 border border-primary/20 rounded-2xl p-4 shadow-inner">
                                <div className="text-[10px] font-bold text-primary/60 uppercase tracking-wider mb-2">Live Search Query</div>
                                <p className="text-sm font-mono font-medium text-foreground leading-relaxed italic">
                                    "{typeof worker.queries?.[0] === 'string' ? worker.queries[0] : (worker.queries?.[0] as any)?.query || 'Wait for next cycle...'}"
                                </p>
                            </div>
                        </div>

                        {/* Query History */}
                        <div className="space-y-4">
                            <h3 className="text-sm font-semibold flex items-center gap-2 text-foreground">
                                <History className="w-4 h-4 text-primary" />
                                Execution History
                            </h3>
                            <div className="space-y-2">
                                {queryHistory.length > 0 ? (
                                    queryHistory.map((q, i) => (
                                        <div key={i} className="flex items-center justify-between p-3 bg-muted/20 border rounded-xl text-xs">
                                            <div className="flex-1 min-w-0 pr-4">
                                                <div className="font-mono text-foreground truncate">"{q.query}"</div>
                                                <div className="text-[10px] text-muted-foreground mt-1">Iteration {q.iteration}</div>
                                            </div>
                                            <div className="flex gap-4 text-right">
                                                <div>
                                                    <div className="text-[10px] font-bold text-muted-foreground uppercase">Found</div>
                                                    <div className="font-semibold">{q.results_count || 0}</div>
                                                </div>
                                                <div>
                                                    <div className="text-[10px] font-bold text-muted-foreground uppercase">New</div>
                                                    <div className="font-semibold text-primary">{q.new_entities || 0}</div>
                                                </div>
                                            </div>
                                        </div>
                                    )).reverse()
                                ) : (
                                    <div className="text-sm text-center py-4 bg-muted/10 rounded-xl border-2 border-dashed text-muted-foreground italic">
                                        No queries recorded yet
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Recent Discoveries / Domains */}
                        {searchHistory.length > 0 && (
                            <div className="space-y-4">
                                <h3 className="text-sm font-semibold flex items-center gap-2 text-foreground">
                                    <Search className="w-4 h-4 text-primary" />
                                    Search Engine Performance
                                </h3>
                                <div className="grid grid-cols-2 gap-3">
                                    {searchHistory.slice(-4).map((s, i) => (
                                        <div key={i} className="p-3 bg-primary/5 rounded-xl border border-primary/10">
                                            <div className="flex items-center justify-between mb-1">
                                                <span className="text-[10px] font-bold uppercase text-primary/70">{s.engine}</span>
                                                <Globe className="w-3 h-3 text-primary/50" />
                                            </div>
                                            <div className="text-xs font-medium truncate mb-2">"{s.query}"</div>
                                            <div className="flex gap-3 text-[10px] font-bold">
                                                <span className="text-muted-foreground">{s.results} results</span>
                                                <span className="text-green-600">+{s.new_entities} new</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* URL Queue */}
                        {worker.personal_queue.length > 0 && (
                            <div className="space-y-4 pb-4">
                                <h3 className="text-sm font-semibold flex items-center gap-2 text-foreground">
                                    <ListOrdered className="w-4 h-4 text-primary" />
                                    URL Queue ({worker.personal_queue.length})
                                </h3>
                                <div className="space-y-2">
                                    {worker.personal_queue.slice(0, 5).map((url, i) => (
                                        <div key={i} className="flex items-center gap-2 p-2.5 bg-muted/10 rounded-lg border group hover:border-primary/30 transition-colors">
                                            <ChevronRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary" />
                                            <span className="text-xs font-mono text-muted-foreground truncate flex-1">
                                                {url}
                                            </span>
                                        </div>
                                    ))}
                                    {worker.personal_queue.length > 5 && (
                                        <div className="text-[10px] text-center text-muted-foreground pt-1">
                                            + {worker.personal_queue.length - 5} more URLs in queue
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <div className="p-4 border-t bg-muted/10 text-right">
                    <button
                        onClick={onClose}
                        className="px-6 py-2 bg-primary text-primary-foreground font-semibold rounded-xl hover:shadow-lg transition-all"
                    >
                        Dismiss
                    </button>
                </div>
            </div>
        </div>
    );
};
