import React, { useEffect, useRef } from 'react';

interface Props {
    logs: string[];
}

export const LogStream: React.FC<Props> = ({ logs }) => {
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 50;

        if (isAtBottom) {
            bottomRef.current?.scrollIntoView({ behavior: 'auto', block: 'nearest' });
        }
    }, [logs]);

    return (
        <div className="bg-card border rounded-2xl p-6 h-[400px] flex flex-col">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
                Live Activity Log
            </h3>
            <div
                ref={scrollContainerRef}
                className="flex-1 overflow-y-auto space-y-2 font-mono text-xs pr-2 overscroll-contain"
            >
                {logs.map((log, i) => (
                    <div key={i} className="py-1 px-2 hover:bg-muted/50 rounded transition-colors break-words">
                        <span className="text-muted-foreground mr-2">[{i + 1}]</span>
                        {log}
                    </div>
                ))}
                <div ref={bottomRef} />
            </div>
        </div>
    );
};
