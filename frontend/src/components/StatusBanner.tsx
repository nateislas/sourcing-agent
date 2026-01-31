import React from 'react';
import type { ResearchState } from '../types';
import { Activity, CheckCircle, AlertCircle, Clock } from 'lucide-react';

interface Props {
    status: ResearchState['status'];
    topic: string;
}

const statusConfig = {
    initialized: { icon: Clock, color: 'text-blue-500', bg: 'bg-blue-500/10', label: 'Initializing' },
    running: { icon: Activity, color: 'text-amber-500', bg: 'bg-amber-500/10', label: 'Researching' },
    verification_pending: { icon: Activity, color: 'text-purple-500', bg: 'bg-purple-500/10', label: 'Verifying' },
    completed: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-500/10', label: 'Completed' },
    failed: { icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-500/10', label: 'Failed' },
    killed: { icon: AlertCircle, color: 'text-orange-500', bg: 'bg-orange-500/10', label: 'Killed' },
    cancelled: { icon: AlertCircle, color: 'text-gray-500', bg: 'bg-gray-500/10', label: 'Cancelled' },
    timed_out: { icon: Clock, color: 'text-amber-700', bg: 'bg-amber-700/10', label: 'Timed Out' },
};

export const StatusBanner: React.FC<Props> = ({ status, topic }) => {
    const config = statusConfig[status] || statusConfig.initialized;
    const Icon = config.icon;

    return (
        <div className={`flex items-center justify-between p-6 rounded-2xl border ${config.bg} mb-8`}>
            <div className="flex items-center gap-4">
                <div className={`p-3 rounded-xl bg-background shadow-sm ${config.color}`}>
                    <Icon className="w-6 h-6" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-foreground">{topic}</h1>
                    <p className={`text-sm font-medium ${config.color} uppercase tracking-wider`}>
                        {config.label}
                    </p>
                </div>
            </div>
        </div>
    );
};
