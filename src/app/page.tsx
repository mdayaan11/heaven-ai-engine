import React from 'react';
import clientData from './content.json';

export default function HomePage() {
  // Use optional chaining and fallback to empty array to prevent crashes
  const features = clientData?.features || [];

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-sans overflow-x-hidden">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[600px] bg-gradient-to-b from-orange-500/10 via-transparent to-transparent blur-3xl pointer-events-none" />
      
      <header className="relative max-w-6xl mx-auto px-6 py-6 flex justify-between items-center border-b border-neutral-900 z-20">
        <span className="text-xl font-black tracking-wider text-white uppercase">
          {clientData.businessName || "Heaven AI"}
        </span>
      </header>

      <main className="relative max-w-5xl mx-auto pt-24 pb-16 px-6 text-center z-10">
        <h1 className={`text-5xl md:text-7xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r ${clientData.accentGradients || 'from-amber-500 to-orange-600'}`}>
          {clientData.tagline}
        </h1>
        
        <p className="mt-6 text-lg md:text-xl text-neutral-400 max-w-3xl mx-auto leading-relaxed">
          {clientData.heroDescription}
        </p>
      </main>

      {/* Only show section if features exist */}
      {features.length > 0 && (
        <section className="relative max-w-5xl mx-auto my-16 px-6 z-10">
          <div className="grid md:grid-cols-2 gap-6">
            {features.map((item: any, idx: number) => (
              <div key={idx} className="p-8 rounded-2xl bg-neutral-900/40 border border-neutral-900 backdrop-blur-xl">
                <h3 className="text-xl font-bold text-neutral-100">{item.title}</h3>
                <p className="mt-3 text-neutral-400 text-sm">{item.desc}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
