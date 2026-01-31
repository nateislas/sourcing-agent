import React, { useEffect, useState } from 'react';
import { ResearchForm } from '../components/ResearchForm';
import { getHistory } from '../services/api';
import type { ResearchSessionSummary } from '../types';
import { Clock, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

export const Home: React.FC = () => {
    const [history, setHistory] = useState<ResearchSessionSummary[]>([]);

    useEffect(() => {
        getHistory().then(setHistory).catch(console.error);
    }, []);

    return (
        <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 relative overflow-hidden">
            {/* Background Decor */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
                <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/5 rounded-full blur-[120px]" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-500/5 rounded-full blur-[120px]" />
            </div>

            <div className="w-full max-w-4xl space-y-12">
                <div className="text-center space-y-4">
                    <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-foreground">
                        Deep Research Agent
                    </h1>
                    <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
                        Automated high-dimensional research powered by multi-agent reasoning.
                        Enter a topic to begin a deep scan.
                    </p>
                </div>

                <ResearchForm />

                {history.length > 0 && (
                    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 delay-200">
                        <div className="flex items-center gap-2 mb-4 text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                            <Clock className="w-4 h-4" />
                            Recent Sessions
                        </div>
                        <div className="grid gap-3">
                            {history.map((session) => (
                                <Link
                                    key={session.session_id}
                                    to={`/research/${session.session_id}`}
                                    className="group flex items-center justify-between p-4 bg-card border rounded-xl hover:shadow-md hover:border-primary/50 transition-all duration-300"
                                >
                                    <div>
                                        <div className="font-medium text-foreground group-hover:text-primary transition-colors">
                                            {session.topic}
                                        </div>
                                        <div className="text-xs text-muted-foreground flex gap-2 mt-1">
                                            <span>
                                                {session.created_at
                                                    ? new Date(session.created_at).toLocaleDateString()
                                                    : 'No date'}
                                            </span>
                                            <span>•</span>
                                            <span className={(
                                                {
                                                    completed: 'text-green-600',
                                                    running: 'text-amber-600',
                                                    failed: 'text-red-600',
                                                    verification_pending: 'text-purple-600',
                                                    initialized: 'text-blue-600'
                                                } as Record<string, string>)[session.status] || 'text-muted-foreground'}>
                                                {session.status}
                                            </span>
                                            <span>•</span>
                                            <span>
                                                {session.entities_count} found
                                            </span>
                                            <span>•</span>
                                            <span className="font-mono text-emerald-600">
                                                ${session.total_cost?.toFixed(4) || "0.0000"}
                                            </span>
                                        </div>
                                    </div>
                                    <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
                                </Link>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
