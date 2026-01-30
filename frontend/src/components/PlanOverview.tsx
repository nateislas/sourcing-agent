import React, { useState } from 'react';
import type { ResearchPlan, Entity } from '../types';
import { Lightbulb, Target, ArrowRight, BrainCircuit, ChevronDown, ChevronUp, Fingerprint } from 'lucide-react';

interface Props {
    plan: ResearchPlan;
    entities?: Record<string, Entity>;
}

export const PlanOverview: React.FC<Props> = ({ plan, entities }) => {
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

            {/* Knowledge Graph Vocabulary */}
            {entities && Object.keys(entities).length > 0 && (
                <div className="pt-4 border-t space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                            <Fingerprint className="w-3 h-3" />
                            Knowledge Graph Highlights
                        </div>
                        <div className="text-[10px] text-muted-foreground italic">
                            Agent is mapping {Object.keys(entities).length} unique concepts
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-x-6 gap-y-3">
                        {Object.values(entities)
                            .filter(e => e.mention_count > 1 || e.aliases.length > 1) // Only show "interesting" ones
                            .slice(0, 20)
                            .map((entity, i) => {
                                const hasUniqueAlias = entity.aliases &&
                                    entity.aliases.some(a => a.toLowerCase() !== entity.canonical_name.toLowerCase());
                                const isCodeName = /^[A-Z]{1,4}-\d+/.test(entity.canonical_name);

                                return (
                                    <div key={i} className="flex items-center gap-2 group">
                                        <span className={`text-sm font-medium transition-colors ${isCodeName ? 'text-primary/80 font-mono' : 'text-foreground'
                                            } group-hover:text-primary`}>
                                            {entity.canonical_name}
                                        </span>
                                        {hasUniqueAlias && (
                                            <span className="text-[10px] text-muted-foreground italic bg-muted/50 px-1.5 py-0.5 rounded border border-border/50">
                                                {entity.aliases.find(a => a.toLowerCase() !== entity.canonical_name.toLowerCase())}
                                            </span>
                                        )}
                                    </div>
                                );
                            })
                        }
                    </div>
                </div>
            )}
        </div>
    );
};
