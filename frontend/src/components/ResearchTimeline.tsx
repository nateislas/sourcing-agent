import React from 'react';
import { CheckCircle2, Clock, Search, ShieldCheck, Flag, AlertCircle } from 'lucide-react';
import type { ResearchState } from '../types';

interface Props {
    status: ResearchState['status'];
    iteration: number;
}

export const ResearchTimeline: React.FC<Props> = ({ status, iteration }) => {
    const stages = [
        {
            id: 'init',
            label: 'Preparation',
            icon: Clock,
            isActive: status === 'initialized',
            isDone: ['running', 'verification_pending', 'completed'].includes(status),
            description: 'Initializing research workers and strategy'
        },
        {
            id: 'discovery',
            label: 'Discovery',
            icon: Search,
            isActive: status === 'running' && iteration <= 2,
            isDone: (status === 'running' && iteration > 2) || ['verification_pending', 'completed'].includes(status),
            description: `Broad exploration (Iteration ${Math.min(iteration, 2)})`
        },
        {
            id: 'deep-dive',
            label: 'Deep Dive',
            icon: Flag,
            isActive: status === 'running' && iteration > 2,
            isDone: ['verification_pending', 'completed'].includes(status),
            description: iteration > 2 ? `Targeted extraction (Iteration ${iteration})` : 'Targeted entity extraction'
        },
        {
            id: 'verification',
            label: 'Verification',
            icon: ShieldCheck,
            isActive: status === 'verification_pending',
            isDone: status === 'completed',
            description: 'Cross-referencing and confidence scoring'
        },
        {
            id: 'complete',
            label: 'Completed',
            icon: CheckCircle2,
            isActive: status === 'completed',
            isDone: false,
            description: 'Final report and assets ready'
        }
    ];

    if (['failed', 'killed', 'cancelled', 'timed_out'].includes(status)) {
        const activeIndex = stages.findIndex(s => s.isActive || !s.isDone);
        if (activeIndex !== -1) {
            stages[activeIndex] = {
                ...stages[activeIndex],
                label: 'Failed',
                icon: AlertCircle,
                isActive: true,
                isDone: false,
                description: 'Research process encountered an error'
            };
        }
    }

    return (
        <div className="bg-card border rounded-2xl p-6 shadow-sm overflow-hidden min-h-[120px]">
            <div className="relative flex items-center justify-between">
                {/* Background Line */}
                <div className="absolute top-5 left-0 w-full h-[2px] bg-muted/50 rounded-full" />

                {stages.map((stage, i) => (
                    <div key={stage.id} className="flex-1 flex flex-col items-center relative group">
                        {/* Progress Line (shows line leading TO this node) */}
                        {i > 0 && (
                            <div
                                className={`absolute top-5 right-1/2 w-full h-[2px] transition-all duration-700 ${stage.isDone || stage.isActive ? 'bg-primary' : 'bg-transparent'
                                    }`}
                            />
                        )}

                        {/* Node */}
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-500 border-2 z-10 relative bg-card ${stage.isActive
                            ? 'bg-primary text-primary-foreground border-primary shadow-[0_0_15px_rgba(var(--primary),0.3)]'
                            : stage.isDone
                                ? 'bg-green-50 text-green-600 border-green-200'
                                : 'bg-card text-muted-foreground border-border'
                            }`}>
                            {stage.isDone ? (
                                <CheckCircle2 className="w-5 h-5" />
                            ) : (
                                <stage.icon className={`w-5 h-5 ${stage.isActive ? 'animate-pulse' : ''}`} />
                            )}
                        </div>

                        {/* Label */}
                        <div className="mt-4 flex flex-col items-center">
                            <span className={`text-[10px] font-bold uppercase tracking-widest whitespace-nowrap px-2 pb-1 ${stage.isActive ? 'text-primary' : 'text-muted-foreground'
                                }`}>
                                {stage.label}
                            </span>
                        </div>

                        {/* Tooltip */}
                        <div className="hidden group-hover:block absolute -top-12 left-1/2 -translate-x-1/2 bg-popover text-popover-foreground text-[10px] p-2 rounded shadow-lg border z-30 w-32 text-center pointer-events-none">
                            {stage.description}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
