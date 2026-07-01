import React from 'react';

// Fallback data structure to ensure compilation 
// Your AI engine can either update this object directly or you can swap this back to an import in Vercel
const clientData = {
  businessName: "Heaven AI Hub",
  tagline: "Autonomous Generation",
  heroDescription: "Building the future of web deployment.",
  themeMode: "dark",
  accentGradients: "from-amber-500 to-orange-600",
  features: [
    { title: "Instant Deployment", desc: "Zero-configuration edge hosting." },
    { title: "Dynamic Architecture", desc: "Bulletproof React compilation." }
  ]
};

export default function HomePage() {
  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-sans overflow-x-hidden">
      {/* Background Cinematic Glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[600px] bg-gradient-to-b from-orange-500/10 via-transparent to-transparent blur-3xl pointer-events-none" />
      
      {/* Navbar */}
      <header className="relative max-w-6xl mx-auto px-6 py-6 flex justify-between items-center border-b border-neutral-900 backdrop-blur-md z-20">
        <span className="text-xl font-black tracking-wider text-white uppercase">
          {clientData.businessName}
        </span>
        <button className="px-4 py-2 rounded-lg bg-neutral-900 border border-neutral-800 text-sm font-medium text-neutral-300 hover:text-white transition">
          Connect
        </button>
      </header>

      {/* Hero Section */}
      <main className="relative max-w-5xl mx-auto pt-24 pb-16 px-6 text-center z-10">
        <span className="text-xs font-semibold tracking-widest text-orange-500 uppercase px-3 py-1 bg-orange-500/10 rounded-full border border-orange-500/20">
          Deployed via Heaven AI
        </span>
        
        <h1 className={`mt-6 text-5xl md:text-7xl font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-r ${clientData.accentGradients || 'from-amber-500 to-orange-600'}`}>
          {clientData.tagline}
        </h1>
        
        <p className="mt-6 text-lg md:text-xl text-neutral-400 max-w-3xl mx-auto leading-relaxed">
          {clientData.heroDescription}
        </p>
      </main>

      {/* Dynamic Features Grid */}
      <section className="relative max-w-5xl mx-auto my-16 px-6 z-10">
        <div className="grid md:grid-cols-2 gap-6">
          {clientData.features && clientData.features.map((item: any, idx: number) => (
            <div key={idx} className="p-8 rounded-2xl bg-neutral-900/40 border border-neutral-900 backdrop-blur-xl">
              <h3 className="text-xl font-bold text-neutral-100">{item.title}</h3>
              <p className="mt-3 text-neutral-400 text-sm">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
