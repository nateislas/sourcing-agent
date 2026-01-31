import React from 'react';
import type { Entity } from '../types';
import { ExternalLink, CheckCircle2, HelpCircle, XCircle, Beaker, Building2, Globe, Tag } from 'lucide-react';
import { EntityDetailModal } from './EntityDetailModal';

interface Props {
    entities: Record<string, Entity>;
}

export const ResultsTable: React.FC<Props> = ({ entities }) => {
    const [selectedEntity, setSelectedEntity] = React.useState<Entity | null>(null);
    const statusPriority: Record<string, number> = {
        'VERIFIED': 0,
        'UNVERIFIED': 1,
        'UNCERTAIN': 2,
        'REJECTED': 3
    };

    const entityList = React.useMemo(() =>
        Object.values(entities).sort((a, b) => {
            const priorityA = statusPriority[a.verification_status] ?? 99;
            const priorityB = statusPriority[b.verification_status] ?? 99;

            if (priorityA !== priorityB) {
                return priorityA - priorityB;
            }

            return b.mention_count - a.mention_count;
        }),
        [entities]);

    if (entityList.length === 0) {
        return (
            <div className="bg-card border rounded-2xl p-8 text-center border-dashed">
                <p className="text-muted-foreground">No entities discovered yet. Research is underway...</p>
            </div>
        );
    }

    return (
        <div className="bg-card border rounded-2xl shadow-sm overflow-hidden flex flex-col max-h-[650px] overscroll-contain">
            <div className="overflow-auto flex-1 overscroll-contain">
                <table className="w-full text-sm text-left border-collapse">
                    <thead className="text-[10px] text-muted-foreground uppercase bg-muted/80 backdrop-blur-sm sticky top-0 z-10 border-b tracking-wider">
                        <tr>
                            <th className="px-6 py-4 font-bold text-primary/80">Asset Identifier</th>
                            <th className="px-6 py-4 font-bold text-primary/80">Classification</th>
                            <th className="px-6 py-4 font-bold text-primary/80">Target & Modality</th>
                            <th className="px-6 py-4 font-bold text-primary/80">Origin & Owner</th>
                            <th className="px-6 py-4 font-bold text-primary/80">Metrics</th>
                            <th className="px-6 py-4 font-bold text-primary/80">Status</th>
                            <th className="px-6 py-4 font-bold text-right text-primary/80">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                        {entityList.map((entity) => (
                            <tr
                                key={entity.canonical_name}
                                className="hover:bg-primary/[0.02] transition-all cursor-pointer group"
                                onClick={() => setSelectedEntity(entity)}
                            >
                                {/* Asset Identifier */}
                                <td className="px-6 py-4">
                                    <div className="font-bold text-foreground group-hover:text-primary transition-colors flex items-center gap-2">
                                        {entity.canonical_name}
                                    </div>
                                    <div className="text-[10px] text-muted-foreground truncate max-w-[200px] mt-0.5 font-mono" title={entity.aliases?.join(', ')}>
                                        {entity.aliases?.slice(0, 3).join(', ')}
                                        {entity.aliases?.length > 3 && ` +${entity.aliases.length - 3}`}
                                    </div>
                                </td>

                                {/* Classification */}
                                <td className="px-6 py-4">
                                    <div className="flex flex-col gap-1.5">
                                        {entity.drug_class ? (
                                            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-700">
                                                <Beaker className="w-3 h-3" />
                                                {entity.drug_class}
                                            </span>
                                        ) : (
                                            <span className="text-[10px] text-muted-foreground italic flex items-center gap-1">
                                                <Beaker className="w-3 h-3 opacity-30" />
                                                Unknown Class
                                            </span>
                                        )}
                                        {entity.clinical_phase ? (
                                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-bold bg-purple-100 text-purple-700 border border-purple-200 w-fit">
                                                {entity.clinical_phase}
                                            </span>
                                        ) : (
                                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-bold bg-muted text-muted-foreground border border-border w-fit">
                                                DISCOVERY
                                            </span>
                                        )}
                                    </div>
                                </td>

                                {/* Target & Modality */}
                                <td className="px-6 py-4">
                                    <div className="flex flex-col gap-1">
                                        <div className="flex items-center gap-1.5 min-h-[16px]">
                                            <Tag className="w-3 h-3 text-muted-foreground" />
                                            <span className="text-[11px] font-medium text-foreground">
                                                {entity.attributes?.target || entity.attributes?.Target || <span className="opacity-30 italic text-[10px]">No Target</span>}
                                            </span>
                                        </div>
                                        <div className="text-[10px] text-muted-foreground ml-4">
                                            {entity.attributes?.modality || entity.attributes?.Modality || ""}
                                        </div>
                                    </div>
                                </td>

                                {/* Origin & Owner */}
                                <td className="px-6 py-4">
                                    <div className="flex flex-col gap-1">
                                        <div className="flex items-center gap-1.5">
                                            <Building2 className="w-3 h-3 text-muted-foreground" />
                                            <span className="text-[11px] font-medium text-foreground truncate max-w-[150px]">
                                                {entity.attributes?.owner || entity.attributes?.Owner || <span className="opacity-30 italic text-[10px]">Unknown Owner</span>}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-1.5 ml-0.5">
                                            <Globe className="w-2.5 h-2.5 text-muted-foreground/60" />
                                            <span className="text-[10px] text-muted-foreground">
                                                {entity.attributes?.geography || entity.attributes?.Geography || "Unspecified"}
                                            </span>
                                        </div>
                                    </div>
                                </td>

                                {/* Metrics */}
                                <td className="px-6 py-4 font-mono">
                                    <div className="flex flex-col gap-0.5">
                                        <div className="flex items-baseline gap-1">
                                            <span className="text-sm font-bold text-foreground">{entity.mention_count}</span>
                                            <span className="text-[9px] text-muted-foreground uppercase">Mentions</span>
                                        </div>
                                        <div className="text-[9px] text-primary font-bold">
                                            {entity.evidence.length} SOURCES
                                        </div>
                                    </div>
                                </td>

                                {/* Status */}
                                <td className="px-6 py-4">
                                    <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-lg border text-[10px] font-bold tracking-tight ${entity.verification_status === 'VERIFIED'
                                        ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                                        : entity.verification_status === 'REJECTED'
                                            ? 'bg-rose-50 text-rose-700 border-rose-100'
                                            : 'bg-amber-50 text-amber-700 border-amber-100'
                                        }`}>
                                        {entity.verification_status === 'VERIFIED' && <CheckCircle2 className="w-3.5 h-3.5" />}
                                        {(entity.verification_status === 'UNVERIFIED' || entity.verification_status === 'UNCERTAIN') && <HelpCircle className="w-3.5 h-3.5" />}
                                        {entity.verification_status === 'REJECTED' && <XCircle className="w-3.5 h-3.5" />}
                                        {entity.verification_status}
                                    </div>
                                </td>

                                {/* Actions */}
                                <td className="px-6 py-4 text-right">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setSelectedEntity(entity);
                                        }}
                                        className="text-muted-foreground hover:text-primary hover:bg-primary/5 transition-all p-2 rounded-lg"
                                        title="View Detailed Evidence"
                                    >
                                        <ExternalLink className="w-4 h-4" />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <EntityDetailModal
                entity={selectedEntity}
                isOpen={!!selectedEntity}
                onClose={() => setSelectedEntity(null)}
            />
        </div>
    );
};
