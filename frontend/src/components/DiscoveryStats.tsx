import React from 'react';
import type { WorkerState } from '../types';
import { TrendingUp, Target, Zap } from 'lucide-react';

interface Props {
    workers: Record<string, WorkerState>;
}

export const DiscoveryStats: React.FC<Props> = ({ workers }) => {
    const workerList = Object.values(workers);

    // Calculate aggregate metrics
    const totalPages = workerList.reduce((sum, w) => sum + w.pages_fetched, 0);
    const totalEntities = workerList.reduce((sum, w) => sum + w.entities_found, 0);
    const yieldRate = totalPages > 0 ? (totalEntities / totalPages).toFixed(2) : '0';

    // Aggregate new entities by iteration
    const iterationData: Record<number, number> = {};
    workerList.forEach(w => {
        w.query_history?.forEach(q => {
            const iter = q.iteration || 1;
            iterationData[iter] = (iterationData[iter] || 0) + (q.new_entities || 0);
        });
    });

    const iterations = Object.keys(iterationData)
        .map(Number)
        .sort((a, b) => a - b);

    const maxEntities = Math.max(...Object.values(iterationData), 10);

    return (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Velocity Chart */}
            <div className="md:col-span-2 bg-card border rounded-2xl p-5 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                        <TrendingUp className="w-3.5 h-3.5 text-primary" />
                        Discovery Velocity
                    </h3>
                    <span className="text-[10px] font-mono text-muted-foreground">New Assets / Iteration</span>
                </div>

                <div className="h-24 flex items-end gap-2 px-2 mt-2">
                    {iterations.length > 0 ? iterations.map(iter => (
                        <div key={iter} className="flex-1 flex flex-col items-center gap-2 group relative">
                            <div
                                className="w-full bg-primary/20 rounded-t-lg group-hover:bg-primary/40 transition-all duration-500 relative overflow-hidden"
                                style={{ height: `${(iterationData[iter] / maxEntities) * 100}%` }}
                            >
                                <div className="absolute inset-0 bg-primary/20 animate-pulse" />
                            </div>
                            <span className="text-[10px] font-bold text-muted-foreground">i{iter}</span>

                            {/* Tooltip */}
                            <div className="absolute -top-8 bg-foreground text-background text-[10px] font-bold py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                                +{iterationData[iter]}
                            </div>
                        </div>
                    )) : (
                        <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground italic border-2 border-dashed rounded-xl">
                            Awaiting iteration data...
                        </div>
                    )}
                </div>
            </div>

            {/* Efficiency Score */}
            <div className="bg-card border rounded-2xl p-5 shadow-sm flex flex-col justify-between">
                <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    Yield
                </h3>
                <div className="space-y-1">
                    <div className="text-3xl font-bold text-foreground">
                        {yieldRate}
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                        Assets per Page
                    </div>
                </div>
            </div>

            {/* Total Coverage */}
            <div className="bg-card border rounded-2xl p-5 shadow-sm flex flex-col justify-between">
                <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                    <Target className="w-3.5 h-3.5 text-blue-500" />
                    Recall
                </h3>
                <div className="space-y-1">
                    <div className="text-3xl font-bold text-foreground">
                        {totalEntities}
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                        Total Discoveries
                    </div>
                </div>
            </div>
        </div>
    );
};
