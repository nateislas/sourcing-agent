import React from 'react';
import type { WorkerState } from '../types';
import { Target, Zap } from 'lucide-react';

interface Props {
    workers: Record<string, WorkerState>;
}

export const DiscoveryStats: React.FC<Props> = ({ workers }) => {
    const workerList = Object.values(workers);

    // Calculate aggregate metrics
    const totalPages = workerList.reduce((sum, w) => sum + w.pages_fetched, 0);
    const totalEntities = workerList.reduce((sum, w) => sum + w.entities_found, 0);
    const yieldRate = totalPages > 0 ? (totalEntities / totalPages).toFixed(2) : '0';

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
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
