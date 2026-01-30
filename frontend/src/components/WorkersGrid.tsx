import React from 'react';
import type { WorkerState } from '../types';
import { Bot, FileText, Target } from 'lucide-react';

interface Props {
    workers: Record<string, WorkerState>;
}

import { WorkerDetailModal } from './WorkerDetailModal';

interface Props {
    workers: Record<string, WorkerState>;
}

export const WorkersGrid: React.FC<Props> = ({ workers }) => {
    const [selectedWorker, setSelectedWorker] = React.useState<WorkerState | null>(null);
    const workerList = React.useMemo(() => Object.values(workers), [workers]);

    return (
        <div className="space-y-4">
            <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-[0.2em] mb-4">
                Compute Nodes
            </h3>
            <div className="grid grid-cols-1 gap-4">
                {workerList.map((worker) => {
                    const currentQuery = worker.queries?.[0];
                    const queryText = typeof currentQuery === 'string' ? currentQuery : currentQuery?.query || 'Analyzing targets...';
                    const progress = Math.min((worker.pages_fetched / worker.page_budget) * 100, 100);

                    return (
                        <div
                            key={worker.id}
                            onClick={() => setSelectedWorker(worker)}
                            className="group relative bg-card border rounded-2xl p-5 shadow-sm hover:shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:-translate-y-0.5 transition-all duration-300 cursor-pointer overflow-hidden"
                        >
                            {/* Animated Background Accent */}
                            <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full -mr-16 -mt-16 blur-3xl group-hover:bg-primary/10 transition-colors" />

                            <div className="relative space-y-4">
                                {/* Top Header */}
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2.5 bg-primary/10 rounded-xl text-primary group-hover:scale-110 transition-transform duration-300">
                                            <Bot className="w-5 h-5" />
                                        </div>
                                        <div>
                                            <div className="font-bold text-sm text-foreground tracking-tight leading-none group-hover:text-primary transition-colors">
                                                {worker.strategy.replace(/_/g, ' ')}
                                            </div>
                                            <div className="text-[10px] text-muted-foreground font-mono mt-1 opacity-60">
                                                ID: {worker.id.split('-').pop()}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {worker.status === 'ACTIVE' && (
                                            <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                                        )}
                                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${worker.status === 'ACTIVE' || worker.status === 'PRODUCTIVE'
                                                ? 'bg-green-50 text-green-600 border border-green-200'
                                                : 'bg-muted text-muted-foreground border border-border'
                                            }`}>
                                            {worker.status}
                                        </span>
                                    </div>
                                </div>

                                {/* Main Body - Current Query */}
                                <div className="bg-muted/40 rounded-xl p-4 border border-border/50 group-hover:border-primary/20 transition-colors">
                                    <div className="text-[9px] font-bold text-muted-foreground uppercase tracking-[0.15em] mb-2 flex items-center justify-between">
                                        Current Objective
                                        <span className="text-[8px] opacity-0 group-hover:opacity-100 transition-opacity font-mono text-primary">Live Update</span>
                                    </div>
                                    <div className="text-xs font-medium text-foreground leading-relaxed italic line-clamp-2">
                                        "{queryText}"
                                    </div>
                                </div>

                                {/* Bottom Stats & Progress */}
                                <div className="space-y-3 pt-1">
                                    <div className="flex items-center justify-between">
                                        <div className="flex gap-4">
                                            <div className="flex items-center gap-1.5">
                                                <div className="p-1 bg-blue-50 text-blue-600 rounded">
                                                    <FileText className="w-3 h-3" />
                                                </div>
                                                <span className="text-[11px] font-bold text-muted-foreground">
                                                    {worker.pages_fetched} <span className="font-normal opacity-60">Pages</span>
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-1.5">
                                                <div className="p-1 bg-indigo-50 text-indigo-600 rounded">
                                                    <Target className="w-3 h-3" />
                                                </div>
                                                <span className="text-[11px] font-bold text-muted-foreground">
                                                    {worker.entities_found} <span className="font-normal opacity-60">Assets</span>
                                                </span>
                                            </div>
                                        </div>
                                        <span className="text-[11px] font-bold text-primary tabular-nums">
                                            {Math.round(progress)}%
                                        </span>
                                    </div>

                                    {/* Thicker, custom progress bar */}
                                    <div className="h-2 w-full bg-muted/60 rounded-full overflow-hidden p-[2px] border border-border/50">
                                        <div
                                            className="h-full rounded-full bg-gradient-to-r from-primary to-primary/60 transition-all duration-1000 ease-out relative"
                                            style={{ width: `${progress}%` }}
                                        >
                                            <div className="absolute inset-0 bg-white/20 animate-[shimmer_2s_infinite] -translate-x-full" />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
                {workerList.length === 0 && (
                    <div className="col-span-full py-12 text-center space-y-3 bg-muted/20 border-2 border-dashed rounded-3xl group">
                        <div className="w-12 h-12 bg-muted/50 rounded-2xl mx-auto flex items-center justify-center text-muted-foreground group-hover:rotate-12 transition-transform">
                            <Bot className="w-6 h-6" />
                        </div>
                        <div className="text-sm font-medium text-muted-foreground">
                            Waiting for compute nodes to initialize...
                        </div>
                    </div>
                )}
            </div>

            <WorkerDetailModal
                worker={selectedWorker}
                isOpen={!!selectedWorker}
                onClose={() => setSelectedWorker(null)}
            />
        </div>
    );
};
