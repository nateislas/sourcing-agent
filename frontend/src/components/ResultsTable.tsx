import React from 'react';
import type { Entity } from '../types';
import { ExternalLink, CheckCircle2, HelpCircle, XCircle } from 'lucide-react';
import { EntityDetailModal } from './EntityDetailModal';

interface Props {
    entities: Record<string, Entity>;
}

export const ResultsTable: React.FC<Props> = ({ entities }) => {
    const [selectedEntity, setSelectedEntity] = React.useState<Entity | null>(null);
    const entityList = React.useMemo(() =>
        Object.values(entities).sort((a, b) => b.mention_count - a.mention_count),
        [entities]);

    if (entityList.length === 0) {
        return (
            <div className="bg-card border rounded-2xl p-8 text-center">
                <p className="text-muted-foreground">No entities discovered yet. Research is underway...</p>
            </div>
        );
    }

    return (
        <div className="bg-card border rounded-2xl shadow-sm overflow-hidden flex flex-col max-h-[600px] overscroll-contain">
            <div className="overflow-auto flex-1 overscroll-contain">
                <table className="w-full text-sm text-left border-collapse">
                    <thead className="text-xs text-muted-foreground uppercase bg-muted/80 backdrop-blur-sm sticky top-0 z-10 border-b">
                        <tr>
                            <th className="px-6 py-4 font-semibold text-primary/80">Entity Name</th>
                            <th className="px-6 py-4 font-semibold text-primary/80">Classification</th>
                            <th className="px-6 py-4 font-semibold text-primary/80">Mentions</th>
                            <th className="px-6 py-4 font-semibold text-primary/80">Status</th>
                            <th className="px-6 py-4 font-semibold text-right text-primary/80">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                        {entityList.map((entity) => (
                            <tr
                                key={entity.canonical_name}
                                className="hover:bg-primary/5 transition-all cursor-pointer group"
                                onClick={() => setSelectedEntity(entity)}
                            >
                                <td className="px-6 py-4">
                                    <div className="font-semibold text-foreground group-hover:text-primary transition-colors">{entity.canonical_name}</div>
                                    <div className="text-[10px] text-muted-foreground truncate max-w-[250px] mt-0.5" title={entity.aliases?.join(', ')}>
                                        {entity.aliases?.slice(0, 3).join(', ')}
                                        {entity.aliases?.length > 3 && ` +${entity.aliases.length - 3}`}
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <div className="flex flex-col gap-1">
                                        {entity.drug_class && (
                                            <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700 w-fit border border-blue-100/50">
                                                {entity.drug_class}
                                            </span>
                                        )}
                                        {entity.clinical_phase && (
                                            <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-medium bg-purple-50 text-purple-700 w-fit border border-purple-100/50">
                                                {entity.clinical_phase}
                                            </span>
                                        )}
                                        {!entity.drug_class && !entity.clinical_phase && (
                                            <span className="text-muted-foreground">-</span>
                                        )}
                                    </div>
                                </td>
                                <td className="px-6 py-4 font-mono text-muted-foreground">
                                    <div className="flex flex-col">
                                        <span className="text-foreground font-medium">{entity.mention_count}</span>
                                        <span className="text-[10px] text-muted-foreground uppercase opacity-0 group-hover:opacity-100 transition-opacity">Hits</span>
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <div className="flex items-center gap-1.5">
                                        {entity.verification_status === 'VERIFIED' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                                        {entity.verification_status === 'UNVERIFIED' && <HelpCircle className="w-4 h-4 text-amber-500" />}
                                        {entity.verification_status === 'REJECTED' && <XCircle className="w-4 h-4 text-red-500" />}
                                        <span className={`text-xs font-semibold ${entity.verification_status === 'VERIFIED' ? 'text-green-700' :
                                            entity.verification_status === 'REJECTED' ? 'text-red-700' :
                                                'text-amber-700'
                                            }`}>
                                            {entity.verification_status}
                                        </span>
                                    </div>
                                </td>
                                <td className="px-6 py-4 text-right">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setSelectedEntity(entity);
                                        }}
                                        className="text-primary hover:text-primary-foreground hover:bg-primary transition-all p-2 rounded-lg"
                                        title="View Details"
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
