import React, { useEffect } from 'react';
import type { Entity } from '../types';
import { X, ExternalLink, Calendar, Quote, ShieldCheck, ShieldAlert, HelpCircle } from 'lucide-react';

interface Props {
    entity: Entity | null;
    isOpen: boolean;
    onClose: () => void;
}

export const EntityDetailModal: React.FC<Props> = ({ entity, isOpen, onClose }) => {
    // Prevent background scroll when modal is open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => { document.body.style.overflow = 'unset'; };
    }, [isOpen]);

    if (!isOpen || !entity) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 lg:p-8">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-background/80 backdrop-blur-sm transition-opacity animate-in fade-in duration-300"
                onClick={onClose}
            />

            {/* Modal Content */}
            <div className="relative w-full max-w-4xl max-h-[90vh] bg-card border rounded-3xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-300">

                {/* Header */}
                <div className="p-6 border-b flex items-start justify-between bg-muted/30">
                    <div className="space-y-1">
                        <div className="flex items-center gap-3">
                            <h2 className="text-2xl font-bold text-foreground">
                                {entity.canonical_name}
                            </h2>
                            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${entity.verification_status === 'VERIFIED' ? 'bg-green-500/10 text-green-600' :
                                    entity.verification_status === 'REJECTED' ? 'bg-red-500/10 text-red-600' :
                                        'bg-amber-500/10 text-amber-600'
                                }`}>
                                {entity.verification_status === 'VERIFIED' && <ShieldCheck className="w-3.5 h-3.5" />}
                                {entity.verification_status === 'REJECTED' && <ShieldAlert className="w-3.5 h-3.5" />}
                                {entity.verification_status === 'UNCERTAIN' && <HelpCircle className="w-3.5 h-3.5" />}
                                {entity.verification_status}
                            </div>
                        </div>
                        <div className="text-sm text-muted-foreground">
                            Found across {entity.mention_count} sources
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-muted rounded-xl transition-colors text-muted-foreground hover:text-foreground"
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto overscroll-contain">
                    <div className="p-6 space-y-8">

                        {/* Summary Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            <div className="space-y-1.5">
                                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Classification</span>
                                <div className="flex flex-wrap gap-2">
                                    {entity.drug_class && (
                                        <span className="px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-lg border border-blue-100">
                                            {entity.drug_class}
                                        </span>
                                    )}
                                    {entity.clinical_phase && (
                                        <span className="px-2.5 py-1 bg-purple-50 text-purple-700 text-xs font-medium rounded-lg border border-purple-100">
                                            {entity.clinical_phase}
                                        </span>
                                    )}
                                    {!entity.drug_class && !entity.clinical_phase && <span className="text-sm text-muted-foreground italic">No classification available</span>}
                                </div>
                            </div>

                            <div className="space-y-1.5">
                                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Aliases</span>
                                <div className="text-sm text-foreground flex flex-wrap gap-1.5">
                                    {entity.aliases.map((alias, i) => (
                                        <span key={i} className="px-2 py-0.5 bg-muted rounded border text-xs">
                                            {alias}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {entity.rejection_reason && (
                                <div className="space-y-1.5 lg:col-span-1">
                                    <span className="text-[10px] font-bold text-red-600 uppercase tracking-wider">Rejection Reason</span>
                                    <div className="text-xs text-red-700 bg-red-50 p-2 rounded-lg border border-red-100">
                                        {entity.rejection_reason}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Additional Attributes */}
                        {Object.keys(entity.attributes).length > 0 && (
                            <div className="space-y-3">
                                <h3 className="text-sm font-semibold text-foreground border-b pb-2">Properties</h3>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    {Object.entries(entity.attributes).map(([key, value]) => (
                                        <div key={key} className="flex flex-col gap-1">
                                            <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">{key.replace(/_/g, ' ')}</span>
                                            <span className="text-sm text-foreground font-medium">{value}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Evidence Section */}
                        <div className="space-y-4">
                            <h3 className="text-sm font-semibold text-foreground border-b pb-2 flex items-center gap-2">
                                <Quote className="w-4 h-4 text-primary" />
                                Evidence Snippets
                            </h3>
                            <div className="space-y-4">
                                {entity.evidence.length > 0 ? (
                                    entity.evidence.map((snippet, i) => (
                                        <div key={i} className="bg-muted/30 border rounded-2xl p-4 space-y-3 group hover:border-primary/30 transition-colors">
                                            <p className="text-sm text-foreground leading-relaxed italic">
                                                "{snippet.content}"
                                            </p>
                                            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                                                <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
                                                    <div className="flex items-center gap-1.5">
                                                        <Calendar className="w-3.5 h-3.5" />
                                                        {new Date(snippet.timestamp).toLocaleDateString(undefined, {
                                                            year: 'numeric',
                                                            month: 'short',
                                                            day: 'numeric'
                                                        })}
                                                    </div>
                                                </div>
                                                <a
                                                    href={snippet.source_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="inline-flex items-center gap-1.5 text-primary hover:text-primary/80 font-medium text-xs bg-primary/5 px-3 py-1.5 rounded-lg transition-colors"
                                                >
                                                    View Source <ExternalLink className="w-3.5 h-3.5" />
                                                </a>
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-sm text-muted-foreground italic text-center py-8">
                                        No specific evidence snippets available for this entity.
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="p-4 border-t bg-muted/10 text-right">
                    <button
                        onClick={onClose}
                        className="px-6 py-2 bg-primary text-primary-foreground font-semibold rounded-xl hover:shadow-lg transition-all"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
};
