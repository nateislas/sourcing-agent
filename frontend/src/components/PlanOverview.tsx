import React, { useState } from 'react';
import type { ResearchPlan } from '../types';
import { Lightbulb, Target, ArrowRight, BrainCircuit, ChevronDown, ChevronUp } from 'lucide-react';

interface Props {
    plan: ResearchPlan;
}

export const PlanOverview: React.FC<Props> = ({ plan }) => {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className="bg-card border rounded-2xl p-6 shadow-sm space-y-6">
            {/* Header / Hypothesis */}
            <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-primary uppercase tracking-wider">
                    <Lightbulb className="w-4 h-4" />
                    Current Hypothesis
                </div>
                <h2 className="text-xl font-medium text-foreground leading-relaxed">
                    {plan.current_hypothesis}
                </h2>
            </div>

            {/* Strategic Reasoning (Collapsible) */}
            {plan.reasoning && (
                <div className="bg-muted/30 rounded-xl p-4 border border-border/50">
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="flex items-center gap-2 text-sm font-medium text-foreground w-full hover:text-primary transition-colors"
                    >
                        <BrainCircuit className="w-4 h-4" />
                        <span>Strategic Reasoning</span>
                        {expanded ? <ChevronUp className="w-4 h-4 ml-auto" /> : <ChevronDown className="w-4 h-4 ml-auto" />}
                    </button>

                    {expanded && (
                        <div className="mt-3 text-sm text-muted-foreground leading-relaxed pl-6 border-l-2 border-primary/20">
                            {plan.reasoning}
                        </div>
                    )}
                </div>
            )}

            <div className="grid md:grid-cols-2 gap-6 pt-2">
                {/* Knowledge Gaps */}
                <div className="space-y-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        <Target className="w-3 h-3" />
                        Identified Gaps
                    </div>
                    {plan.gaps.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                            {plan.gaps.map((gap, i) => (
                                <div
                                    key={i}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${gap.priority === 'high'
                                        ? 'bg-red-50 text-red-700 border-red-200'
                                        : gap.priority === 'medium'
                                            ? 'bg-amber-50 text-amber-700 border-amber-200'
                                            : 'bg-blue-50 text-blue-700 border-blue-200'
                                        }`}
                                    title={gap.reasoning}
                                >
                                    {gap.description}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground italic">No specific gaps identified yet.</p>
                    )}
                </div>

                {/* Next Steps */}
                <div className="space-y-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        <ArrowRight className="w-3 h-3" />
                        Next Steps
                    </div>
                    <ul className="space-y-2">
                        {plan.next_steps.map((step, i) => (
                            <li key={i} className="text-sm text-foreground flex items-start gap-2">
                                <span className="text-primary/50 mt-1">•</span>
                                {step}
                            </li>
                        ))}
                    </ul>
                </div>
            </div>


        </div>
    );
};
