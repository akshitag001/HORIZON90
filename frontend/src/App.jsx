import React, { useState, useEffect } from 'react';
import { sampleRequests } from './sampleData';
import { Upload, ChevronRight, X, Play, Clock, CheckCircle2, AlertCircle } from 'lucide-react';

export default function App() {
  const [state, setState] = useState('empty'); // 'empty', 'processing', 'results'
  const [activeRequest, setActiveRequest] = useState(null); // Detailed view state
  
  // Processing state variables
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  
  const startProcessing = () => {
    setState('processing');
    setProgress(0);
    setLogs([]);
    
    // Simulate real work
    const steps = [
      "Parsing batch CSV schema...",
      "Resolving historical timelines for user_01...",
      "Converting ZAR → home currency...",
      "Projecting recurring salary events...",
      "Applying 90-day safety forecast (user_01)...",
      "Checking 3rd-party payment options (installments)...",
      "Resolving historical timelines for user_02...",
      "Cross-checking payment options...",
      "Enforcing minimum balance floor (user_02)...",
      "Finalizing batch recommendations..."
    ];
    
    let currentStep = 0;
    const interval = setInterval(() => {
      if (currentStep < steps.length) {
        setLogs(prev => [...prev, steps[currentStep]]);
        setProgress(Math.floor(((currentStep + 1) / steps.length) * 100));
        currentStep++;
      } else {
        clearInterval(interval);
        setTimeout(() => setState('results'), 600);
      }
    }, 400);
  };

  const getStatusConfig = (status) => {
    switch(status) {
      case 'affordable_now':
        return { label: 'Safe to pay today', color: 'bg-brand-safe border-brand-safe text-white', icon: <CheckCircle2 size={16} className="mr-2" /> };
      case 'affordable_with_plan':
        return { label: 'Requires plan', color: 'bg-[#E2952E] border-[#E2952E] text-white', icon: <Clock size={16} className="mr-2" /> };
      case 'affordable_later':
        return { label: 'Wait to pay', color: 'bg-[#4B688A] border-[#4B688A] text-white', icon: <Clock size={16} className="mr-2" /> };
      case 'not_affordable':
        return { label: 'Not affordable', color: 'bg-brand-risk border-brand-risk text-white', icon: <AlertCircle size={16} className="mr-2" /> };
      default:
        return { label: 'Unknown', color: 'bg-gray-500 border-gray-500 text-white', icon: null };
    }
  };

  const formatCurrency = (amt) => {
    return new Intl.NumberFormat('en-US', { style: 'decimal', minimumFractionDigits: 2 }).format(amt);
  };
  
  const formatPlan = (planStr) => {
    if (!planStr || planStr === 'none') return null;
    return planStr.split('|').map((part, i) => {
      const [date, amt] = part.split(':');
      return (
        <div key={i} className="flex justify-between items-center py-2 border-b border-brand-border last:border-0 text-sm">
          <span className="font-mono">{date}</span>
          <span className="font-mono font-medium">{formatCurrency(amt)}</span>
        </div>
      );
    });
  };

  const formatChanges = (changesStr) => {
    if (!changesStr || changesStr === 'none') return 'None required.';
    // Convert 'stop:event_123' to readable text
    return changesStr.split('|').map(c => {
      if (c.startsWith('stop:')) return `Stop recurring expense: ${c.split(':')[1]}`;
      if (c.startsWith('reduce_to:')) return `Reduce expense ${c.split(':')[1]} to ${c.split(':')[2]}`;
      return c;
    }).join(', ');
  };

  return (
    <div className="max-w-5xl mx-auto p-6 md:p-12 relative min-h-screen flex flex-col">
      <header className="mb-12">
        <h1 className="text-2xl font-semibold tracking-tight text-brand-text">Solvent Affordability Engine</h1>
      </header>

      {/* 1. EMPTY STATE */}
      {state === 'empty' && (
        <div className="flex-1 flex flex-col justify-center max-w-2xl">
          <div className="border border-brand-border bg-brand-surface rounded-sm p-8 shadow-sm">
            <h2 className="text-lg font-medium mb-6">Evaluate a purchase</h2>
            <div className="mb-6">
              <label className="block text-sm font-medium mb-2 text-brand-muted">Ask anything...</label>
              <textarea 
                className="w-full border border-brand-border p-3 rounded-sm font-sans focus:outline-none focus:border-brand-text resize-none"
                rows="3"
                placeholder="e.g. Can I afford to pay ZAR 12,000 for a laptop today?"
              ></textarea>
            </div>
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <button 
                className="flex items-center text-sm font-medium text-brand-text border border-brand-border px-4 py-2 hover:bg-gray-50 transition-colors"
                onClick={startProcessing}
              >
                <Upload size={16} className="mr-2" />
                Attach requests.csv
              </button>
              <button 
                className="bg-brand-text text-white px-6 py-2 text-sm font-medium hover:bg-black transition-colors"
                onClick={startProcessing}
              >
                Analyze request
              </button>
            </div>
          </div>
          <div className="mt-6 text-center">
            <button 
              onClick={startProcessing}
              className="text-sm font-medium text-brand-muted hover:text-brand-text inline-flex items-center"
            >
              <Play size={14} className="mr-1" /> Run the sample batch
            </button>
          </div>
        </div>
      )}

      {/* 2. PROCESSING STATE */}
      {state === 'processing' && (
        <div className="flex-1 flex flex-col justify-center max-w-2xl mx-auto w-full">
          <div className="mb-8">
            <h2 className="text-xl font-medium mb-2">Simulating 90-day cash flows</h2>
            <p className="text-brand-muted font-mono text-sm mb-4">Request {Math.min(Math.ceil((progress/100)*5), 5)} of 5 analyzed</p>
            
            {/* Progress Bar */}
            <div className="w-full h-2 bg-gray-200 border-x border-brand-border">
              <div 
                className="h-full bg-brand-text transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          </div>
          
          <div className="border border-brand-border bg-brand-surface p-6 font-mono text-xs text-brand-text min-h-[200px] overflow-hidden relative">
            <p className="text-brand-muted mb-4 font-sans font-medium uppercase tracking-wider text-[10px]">Active constraints</p>
            <div className="space-y-2">
              {logs.map((log, i) => (
                <div key={i} className="flex animate-[fadeIn_0.2s_ease-in-out]">
                  <span className="text-brand-muted mr-3">&gt;</span>
                  <span>{log}</span>
                </div>
              ))}
            </div>
            {/* Fade out bottom edge if too many logs */}
            <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-brand-surface to-transparent"></div>
          </div>
        </div>
      )}

      {/* 3. RESULTS GRID */}
      {state === 'results' && (
        <div className="flex-1">
          <div className="mb-8 flex justify-between items-end border-b border-brand-border pb-4">
            <h2 className="text-xl font-medium">5 Requests Evaluated</h2>
            <div className="flex space-x-2">
              <span className="text-xs font-medium uppercase tracking-wider text-brand-muted">Filter:</span>
              <button className="text-xs font-medium text-brand-text">All</button>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {sampleRequests.map((req) => {
              const cfg = getStatusConfig(req.affordability_status);
              return (
                <div 
                  key={req.request_id}
                  onClick={() => setActiveRequest(req)}
                  className="group flex border border-brand-border bg-brand-surface cursor-pointer hover:border-brand-text transition-colors"
                >
                  {/* Structural status indicator line */}
                  <div className={`w-3 shrink-0 ${cfg.color}`}></div>
                  
                  <div className="p-5 flex-1 flex flex-col">
                    <div className="flex justify-between items-start mb-4">
                      <span className="font-mono text-sm font-medium">{req.request_id}</span>
                      <span className="text-xs font-sans font-medium capitalize text-brand-muted">{req.request_type.replace('_', ' ')}</span>
                    </div>
                    
                    <h3 className="font-medium text-brand-text text-sm mb-1 line-clamp-2 min-h-[40px]">{req.request_text}</h3>
                    <div className="font-mono text-lg mb-6">
                      {formatCurrency(req.requested_amount)}
                    </div>
                    
                    <div className="mt-auto">
                      <div className="inline-flex items-center text-[11px] uppercase tracking-wider font-semibold mb-3">
                        <span className={`w-2 h-2 rounded-full mr-2 ${cfg.color.split(' ')[0]}`}></span>
                        {cfg.label}
                      </div>
                      <p className="text-sm text-brand-muted line-clamp-2">
                        {req.decision_explanation}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 4. DETAIL VIEW (Slide-over / Modal) */}
      {activeRequest && (
        <div className="fixed inset-0 z-50 flex justify-end bg-brand-bg/80 backdrop-blur-sm">
          <div className="w-full max-w-xl bg-brand-surface h-full border-l border-brand-border shadow-2xl flex flex-col animate-[slideIn_0.3s_ease-out]">
            {/* Header */}
            <div className="flex justify-between items-center p-6 border-b border-brand-border">
              <div>
                <span className="font-mono text-sm font-medium block">{activeRequest.request_id}</span>
                <span className="text-xs font-sans font-medium capitalize text-brand-muted block mt-1">{activeRequest.request_type.replace('_', ' ')}</span>
              </div>
              <button 
                onClick={() => setActiveRequest(null)}
                className="p-2 border border-brand-border hover:bg-brand-bg transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            
            {/* Body */}
            <div className="flex-1 overflow-y-auto p-8">
              <div className="mb-10">
                <p className="text-lg font-medium text-brand-text mb-4 leading-relaxed">"{activeRequest.request_text}"</p>
                <div className="flex justify-between items-end border-b border-brand-border pb-2">
                  <span className="text-sm font-medium text-brand-muted uppercase tracking-wider">Requested</span>
                  <span className="font-mono text-xl">{formatCurrency(activeRequest.requested_amount)}</span>
                </div>
              </div>
              
              <div className="mb-10">
                <div className="inline-flex items-center text-xs font-bold uppercase tracking-wider mb-6">
                  <span className={`w-3 h-3 mr-2 ${getStatusConfig(activeRequest.affordability_status).color.split(' ')[0]}`}></span>
                  Status: {getStatusConfig(activeRequest.affordability_status).label}
                </div>
                
                <h4 className="text-sm font-medium text-brand-muted uppercase tracking-wider mb-3">Recommendation</h4>
                <p className="text-brand-text text-base leading-relaxed mb-6 bg-brand-bg p-4 border-l-4 border-brand-text">
                  {activeRequest.decision_explanation}
                </p>
                
                {activeRequest.payment_plan !== 'none' && (
                  <div className="mb-8">
                    <h4 className="text-sm font-medium text-brand-muted uppercase tracking-wider mb-3 border-b border-brand-border pb-2">Payment Schedule</h4>
                    <div className="bg-brand-bg p-4 border border-brand-border">
                      {formatPlan(activeRequest.payment_plan)}
                    </div>
                  </div>
                )}
                
                <div className="grid grid-cols-2 gap-6 pt-6 border-t border-brand-border">
                  <div>
                    <h4 className="text-xs font-medium text-brand-muted uppercase tracking-wider mb-2">Safe Capacity Today</h4>
                    <span className="font-mono text-base">{formatCurrency(activeRequest.amount_safe_to_pay)}</span>
                  </div>
                  {activeRequest.earliest_date_for_full_payment && (
                    <div>
                      <h4 className="text-xs font-medium text-brand-muted uppercase tracking-wider mb-2">Earliest Full Payment</h4>
                      <span className="font-mono text-base">{activeRequest.earliest_date_for_full_payment}</span>
                    </div>
                  )}
                  <div className="col-span-2">
                    <h4 className="text-xs font-medium text-brand-muted uppercase tracking-wider mb-2">Spending Changes Required</h4>
                    <span className="text-sm text-brand-text">{formatChanges(activeRequest.spending_changes_needed)}</span>
                  </div>
                </div>
              </div>
              
              {/* Evidence / Grounding block */}
              <div className="border border-brand-border">
                <details className="group">
                  <summary className="cursor-pointer p-4 font-medium text-sm flex items-center bg-brand-bg select-none">
                    <ChevronRight size={16} className="mr-2 group-open:rotate-90 transition-transform" />
                    View cash-flow evidence
                  </summary>
                  <div className="p-4 bg-brand-surface border-t border-brand-border font-mono text-xs space-y-3">
                    <div className="flex justify-between text-brand-text">
                      <span>Base balance available:</span>
                      <span>[Derived from profiles]</span>
                    </div>
                    <div className="flex justify-between text-brand-muted">
                      <span>Protected minimum balance:</span>
                      <span>[Derived from profiles]</span>
                    </div>
                    <div className="border-t border-dashed border-brand-border my-2"></div>
                    <div className="flex justify-between font-medium">
                      <span>Projected constraints (90 days):</span>
                      <span></span>
                    </div>
                    <div className="flex justify-between text-brand-muted">
                      <span>Found 14 recurring events</span>
                      <span></span>
                    </div>
                    <div className="flex justify-between text-brand-muted">
                      <span>Evaluated {activeRequest.allows_partial_payment === 'true' ? 'partial and full options' : 'full options only'}</span>
                      <span></span>
                    </div>
                    <p className="text-[10px] text-brand-muted font-sans mt-4 italic">
                      * Evidence points are synthesized from {activeRequest.user_id}'s financial_events.csv and profiles.
                    </p>
                  </div>
                </details>
              </div>
              
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
