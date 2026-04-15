import React from 'react';
import { LayoutGrid, ArrowRight } from 'lucide-react';

interface LandingPageProps {
  onStart: () => void;
}

const LandingPage: React.FC<LandingPageProps> = ({ onStart }) => {
  return (
    <div className="min-h-screen bg-white flex flex-col font-sans text-slate-900 selection:bg-blue-100">
      {/* Navigation */}
      <nav className="w-full max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white">
            <LayoutGrid size={18} />
          </div>
          <span className="font-bold text-lg tracking-tight">TASKPILOT</span>
        </div>
        
        <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-500">
          <a href="#" className="hover:text-slate-900 transition-colors">Product</a>
          <a href="#" className="hover:text-slate-900 transition-colors">Research</a>
          <a href="#" className="hover:text-slate-900 transition-colors">Safety</a>
        </div>

        <button className="px-5 py-2 rounded-full border border-slate-200 text-sm font-medium hover:border-slate-300 hover:bg-slate-50 transition-all">
          Log in
        </button>
      </nav>

      {/* Hero Section */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 text-center mt-12 md:mt-20">
        
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-100 text-xs font-semibold tracking-wide text-slate-600 mb-8 shadow-sm">
          <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          MULTI-AGENT SYSTEM 2.0
        </div>

        {/* Headline */}
        <h1 className="text-5xl md:text-7xl lg:text-8xl font-semibold tracking-tight text-slate-900 mb-8 max-w-4xl leading-[0.95]">
          Complex tasks, <br className="hidden md:block"/>
          <span className="text-slate-500">orchestrated.</span>
        </h1>

        {/* Subheadline */}
        <p className="text-lg md:text-xl text-slate-500 max-w-2xl font-light leading-relaxed mb-12">
          Experience the calm of structured automation. <br className="hidden md:block" />
          Infinite intelligence, elegantly applied to your workflow.
        </p>

        {/* CTA */}
        <button 
          onClick={onStart}
          className="group relative inline-flex items-center gap-2 px-8 py-4 bg-slate-950 text-white rounded-full text-lg font-medium hover:bg-slate-800 transition-all shadow-xl hover:shadow-2xl hover:-translate-y-0.5"
        >
          Start Task
          <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
        </button>
        <p className="mt-4 text-xs text-slate-400">No credit card required</p>
      </main>

      {/* Trusted By */}
      <footer className="pb-20 pt-12 text-center">
        <p className="text-xs font-semibold tracking-widest text-slate-400 uppercase mb-8">Trusted by visionaries at</p>
        <div className="flex flex-wrap justify-center gap-12 md:gap-24 opacity-40 grayscale">
            {/* Simple SVG Placeholders for Logos to match style */}
            <div className="text-xl font-bold font-serif tracking-widest">VITZ</div>
            <div className="text-xl font-light tracking-[0.3em]">OHZ</div>
            <div className="text-xl font-mono border-2 border-current px-1">OHMI</div>
            <div className="flex items-center gap-1 text-xl font-bold"><span className="w-4 h-4 rotate-45 border border-current"></span>IFT</div>
        </div>
      </footer>
      
      {/* Decorative Gradients (Subtle) */}
      <div className="fixed top-0 left-0 w-full h-full -z-10 overflow-hidden pointer-events-none">
          <div className="absolute top-[-10%] left-[20%] w-[500px] h-[500px] bg-blue-100/40 rounded-full blur-[120px]"></div>
          <div className="absolute bottom-[-10%] right-[10%] w-[600px] h-[600px] bg-purple-100/40 rounded-full blur-[120px]"></div>
      </div>
    </div>
  );
};

export default LandingPage;