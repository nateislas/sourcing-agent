import React, { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { startResearch } from '../services/api';
import { useNavigate } from 'react-router-dom';

export const ResearchForm: React.FC = () => {
    const [topic, setTopic] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!topic.trim()) return;

        setLoading(true);
        try {
            const { session_id } = await startResearch(topic);
            navigate(`/research/${session_id}`);
        } catch (err) {
            console.error(err);
            alert("Failed to start research");
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
            <div className="relative group">
                <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Enter a research topic (e.g., 'CRISPR off-target effects')"
                    className="w-full px-6 py-4 text-lg bg-background border rounded-2xl shadow-sm focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-300 outline-none pr-16 group-hover:shadow-md"
                    disabled={loading}
                />
                <button
                    type="submit"
                    disabled={loading || !topic}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-2 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                </button>
            </div>
        </form>
    );
};
