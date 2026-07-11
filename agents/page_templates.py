"""
Heaven AI — Premium Page Templates
Pre-built, production-quality page.tsx files for common project types.
Gemini picks the type → engine delivers a GUARANTEED beautiful page.
"""
from __future__ import annotations
import re

# ─────────────────────────────────────────────────────────────────────────────
# Type detection from user's idea
# ─────────────────────────────────────────────────────────────────────────────
def detect_project_type(idea: str) -> str:
    """Detect the project type from the user's raw prompt."""
    idea_lower = idea.lower()
    if any(w in idea_lower for w in ("cafe", "coffee", "restaurant", "bakery", "food", "menu", "brunch", "bistro", "diner")):
        return "cafe"
    if any(w in idea_lower for w in ("portfolio", "personal", "resume", "cv", "freelance", "developer")):
        return "portfolio"
    if any(w in idea_lower for w in ("shop", "store", "ecommerce", "e-commerce", "buy", "product", "cart", "shoes", "clothing")):
        return "ecommerce"
    if any(w in idea_lower for w in ("saas", "dashboard", "analytics", "admin", "crm", "project management")):
        return "saas"
    if any(w in idea_lower for w in ("gym", "fitness", "workout", "health", "yoga", "training")):
        return "fitness"
    if any(w in idea_lower for w in ("agency", "studio", "creative", "marketing", "digital")):
        return "agency"
    if any(w in idea_lower for w in ("blog", "news", "magazine", "article", "content")):
        return "blog"
    if any(w in idea_lower for w in ("3d", "three", "animated", "animation", "immersive", "interactive")):
        return "creative"
    return "business"


def get_premium_page(project_type: str, project_name: str) -> str:
    """Get a premium, production-quality page.tsx for the given type."""
    safe = project_name.replace("'", "\\'").replace('"', '\\"')
    templates = {
        "cafe": _cafe_page,
        "portfolio": _portfolio_page,
        "ecommerce": _ecommerce_page,
        "saas": _saas_page,
        "fitness": _fitness_page,
        "agency": _agency_page,
        "creative": _creative_page,
        "blog": _blog_page,
        "business": _business_page,
    }
    fn = templates.get(project_type, _business_page)
    return fn(safe)


# ─────────────────────────────────────────────────────────────────────────────
# CAFE / RESTAURANT
# ─────────────────────────────────────────────────────────────────────────────
def _cafe_page(name: str) -> str:
    return """'use client';

import { useState } from 'react';
import { Coffee, UtensilsCrossed, Clock, MapPin, Star, Phone, ChevronRight, Wine, Cake } from 'lucide-react';

const menuItems = [
  { name: 'Espresso Classico', price: '$4.50', desc: 'Rich double-shot espresso with golden crema', cat: 'coffee' },
  { name: 'Lavender Oat Latte', price: '$6.00', desc: 'Smooth oat milk with house-made lavender syrup', cat: 'coffee' },
  { name: 'Matcha Ceremony', price: '$5.50', desc: 'Ceremonial grade matcha whisked to perfection', cat: 'coffee' },
  { name: 'Cold Brew Tonic', price: '$5.00', desc: '24hr cold brew with sparkling tonic and citrus', cat: 'coffee' },
  { name: 'Truffle Eggs Benedict', price: '$16.00', desc: 'Poached eggs, truffle hollandaise on sourdough', cat: 'food' },
  { name: 'Avocado Garden Toast', price: '$14.00', desc: 'Smashed avo, pomegranate, microgreens, feta', cat: 'food' },
  { name: 'Açaí Power Bowl', price: '$13.00', desc: 'Organic açaí, granola, fresh berries, honey drizzle', cat: 'food' },
  { name: 'Wagyu Smash Burger', price: '$18.00', desc: 'Wagyu beef, aged cheddar, caramelized onions', cat: 'food' },
];

const reviews = [
  { name: 'Sarah M.', text: 'Absolutely stunning atmosphere! The lavender latte changed my life.', stars: 5, avatar: '👩‍🦰' },
  { name: 'James K.', text: 'Best brunch spot in the city. The truffle eggs are unreal.', stars: 5, avatar: '👨‍💼' },
  { name: 'Priya R.', text: 'Beautiful interior, amazing coffee, friendly staff. 10/10!', stars: 5, avatar: '👩‍💻' },
  { name: 'David L.', text: 'The wagyu burger is a must-try. Incredible quality.', stars: 5, avatar: '🧑‍🍳' },
];

const hours = [
  { day: 'Monday - Friday', time: '7:00 AM - 9:00 PM' },
  { day: 'Saturday', time: '8:00 AM - 10:00 PM' },
  { day: 'Sunday', time: '8:00 AM - 8:00 PM' },
];

export default function Home() {
  const [tab, setTab] = useState<'all' | 'coffee' | 'food'>('all');
  const filtered = tab === 'all' ? menuItems : menuItems.filter(i => i.cat === tab);
  const [formSent, setFormSent] = useState(false);

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#0a0a0a] via-[#1a0f0a] to-[#0d0d0d] text-white">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 backdrop-blur-xl bg-black/40 border-b border-amber-900/20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-amber-400 to-orange-500 bg-clip-text text-transparent flex items-center gap-2">
            <Coffee className="w-6 h-6 text-amber-400" /> """ + name + """
          </h1>
          <div className="hidden md:flex gap-8 text-sm text-gray-300">
            {['Menu', 'About', 'Reviews', 'Visit'].map(link => (
              <a key={link} href={`#${link.toLowerCase()}`} className="hover:text-amber-400 transition-colors duration-200">{link}</a>
            ))}
          </div>
          <a href="#visit" className="bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-2 rounded-full text-sm font-semibold hover:scale-105 hover:shadow-lg hover:shadow-amber-500/25 transition-all">
            Reserve Table
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative pt-32 pb-28 px-6 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-amber-900/20 via-transparent to-transparent" />
        <div className="absolute top-20 right-20 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl" />
        <div className="max-w-7xl mx-auto relative z-10">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 rounded-full px-4 py-1.5 text-amber-400 text-sm mb-6 animate-pulse">
              <Star className="w-4 h-4 fill-amber-400" /> Rated #1 Café in the City
            </div>
            <h2 className="text-6xl md:text-8xl font-black leading-[0.9] tracking-tight mb-6">
              Where Every
              <span className="block bg-gradient-to-r from-amber-400 via-orange-400 to-red-400 bg-clip-text text-transparent">
                Sip Tells
              </span>
              A Story
            </h2>
            <p className="text-xl text-gray-400 max-w-xl mb-8 leading-relaxed">
              Artisan coffee, seasonal brunch, and warm ambience — crafted for those who savor the extraordinary.
            </p>
            <div className="flex flex-wrap gap-4">
              <a href="#menu" className="group bg-gradient-to-r from-amber-500 to-orange-600 px-8 py-3.5 rounded-full font-semibold text-lg hover:shadow-lg hover:shadow-amber-500/25 transition-all flex items-center gap-2">
                Explore Menu <ChevronRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </a>
              <a href="#visit" className="border border-gray-700 px-8 py-3.5 rounded-full font-semibold text-lg hover:bg-white/5 transition-all">
                Find Us
              </a>
            </div>
          </div>
          <div className="mt-16 grid grid-cols-3 gap-8 max-w-md">
            {[{ n: '12+', l: 'Years Open' }, { n: '50k+', l: 'Happy Guests' }, { n: '4.9', l: 'Google Rating' }].map(s => (
              <div key={s.l} className="text-center">
                <div className="text-3xl font-bold text-amber-400">{s.n}</div>
                <div className="text-xs text-gray-500 mt-1">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Menu */}
      <section id="menu" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center gap-3 mb-2">
            <UtensilsCrossed className="w-8 h-8 text-amber-400" />
            <h3 className="text-4xl font-bold">Our Menu</h3>
          </div>
          <p className="text-gray-500 mb-8">Crafted with love, served with passion</p>
          <div className="flex gap-3 mb-10">
            {([['all', '✨ All'], ['coffee', '☕ Coffee'], ['food', '🍽️ Food']] as const).map(([key, label]) => (
              <button key={key} onClick={() => setTab(key as any)}
                className={`px-6 py-2.5 rounded-full text-sm font-medium transition-all duration-200 ${tab === key ? 'bg-amber-500 text-black shadow-lg shadow-amber-500/25' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
                {label}
              </button>
            ))}
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5">
            {filtered.map((item, i) => (
              <div key={i} className="group bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 hover:bg-white/[0.06] hover:border-amber-500/30 hover:scale-[1.02] transition-all duration-300 cursor-pointer">
                <div className="flex justify-between items-start mb-3">
                  <h4 className="text-lg font-semibold group-hover:text-amber-400 transition-colors">{item.name}</h4>
                  <span className="text-amber-400 font-bold text-lg">{item.price}</span>
                </div>
                <p className="text-gray-500 text-sm leading-relaxed">{item.desc}</p>
                <div className="mt-4 flex items-center gap-1">
                  {Array.from({ length: 5 }).map((_, j) => (
                    <Star key={j} className="w-3 h-3 fill-amber-400/60 text-amber-400/60" />
                  ))}
                  <span className="text-xs text-gray-600 ml-1">Popular</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* About */}
      <section id="about" className="py-24 px-6 bg-gradient-to-b from-transparent via-amber-950/10 to-transparent">
        <div className="max-w-7xl mx-auto">
          <h3 className="text-4xl font-bold mb-12 text-center">Why Choose Us</h3>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { icon: Coffee, title: 'Single Origin Beans', desc: 'Ethically sourced from Colombia, Ethiopia & Guatemala. Roasted in-house every week for peak freshness.' },
              { icon: UtensilsCrossed, title: 'Farm to Table', desc: 'Seasonal ingredients from local farms. Our menu evolves with the harvest — always fresh, always local.' },
              { icon: Wine, title: 'Evening Bar', desc: 'Natural wines, craft cocktails & artisan cheese boards. Our evening menu transforms the space.' },
            ].map((card, i) => (
              <div key={i} className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-8 hover:border-amber-500/30 hover:scale-[1.02] transition-all duration-300">
                <div className="w-14 h-14 rounded-xl bg-amber-500/10 flex items-center justify-center mb-5">
                  <card.icon className="w-7 h-7 text-amber-400" />
                </div>
                <h4 className="text-xl font-bold mb-3">{card.title}</h4>
                <p className="text-gray-500 leading-relaxed">{card.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Reviews */}
      <section id="reviews" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <h3 className="text-4xl font-bold mb-3">What Our Guests Say</h3>
          <p className="text-gray-500 mb-12">Join thousands of happy customers</p>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {reviews.map((r, i) => (
              <div key={i} className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 hover:border-amber-500/20 transition-all duration-300">
                <div className="flex gap-1 mb-3">
                  {Array.from({ length: r.stars }).map((_, j) => (
                    <Star key={j} className="w-4 h-4 fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <p className="text-gray-300 mb-4 italic text-sm leading-relaxed">&ldquo;{r.text}&rdquo;</p>
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{r.avatar}</span>
                  <span className="text-sm text-amber-400 font-semibold">{r.name}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Hours + Contact */}
      <section id="visit" className="py-24 px-6 bg-gradient-to-t from-amber-950/20 to-transparent">
        <div className="max-w-7xl mx-auto grid md:grid-cols-2 gap-12">
          <div>
            <h3 className="text-4xl font-bold mb-8">Visit Us</h3>
            <div className="space-y-4 text-gray-400 mb-8">
              <p className="flex items-center gap-3"><MapPin className="w-5 h-5 text-amber-400 shrink-0" /> 42 Artisan Lane, Downtown District</p>
              <p className="flex items-center gap-3"><Phone className="w-5 h-5 text-amber-400 shrink-0" /> (555) 123-4567</p>
            </div>
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6">
              <h4 className="font-bold mb-4 flex items-center gap-2"><Clock className="w-5 h-5 text-amber-400" /> Opening Hours</h4>
              {hours.map((h, i) => (
                <div key={i} className="flex justify-between py-2 border-b border-white/[0.04] last:border-0">
                  <span className="text-gray-400">{h.day}</span>
                  <span className="text-amber-400 font-medium">{h.time}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-8">
            <h4 className="text-xl font-bold mb-6">Reserve a Table</h4>
            {formSent ? (
              <div className="text-center py-12">
                <div className="text-5xl mb-4">🎉</div>
                <h5 className="text-xl font-bold text-amber-400 mb-2">Reservation Confirmed!</h5>
                <p className="text-gray-400">We&apos;ll send you a confirmation email shortly.</p>
                <button onClick={() => setFormSent(false)} className="mt-4 text-sm text-amber-400 underline">Make another</button>
              </div>
            ) : (
              <form className="space-y-4" onSubmit={e => { e.preventDefault(); setFormSent(true); }}>
                <input type="text" placeholder="Your Name" required className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500/50 transition-all" />
                <input type="email" placeholder="Email Address" required className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500/50 transition-all" />
                <div className="grid grid-cols-2 gap-3">
                  <input type="date" required className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-amber-500 focus:outline-none transition-all" />
                  <select className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-gray-400 focus:border-amber-500 focus:outline-none transition-all">
                    <option>2 Guests</option>
                    <option>3 Guests</option>
                    <option>4 Guests</option>
                    <option>5+ Guests</option>
                  </select>
                </div>
                <button type="submit" className="w-full bg-gradient-to-r from-amber-500 to-orange-600 py-3.5 rounded-xl font-semibold hover:shadow-lg hover:shadow-amber-500/25 transition-all hover:scale-[1.01]">
                  Book Now ✨
                </button>
              </form>
            )}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] py-10 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-2">
            <Coffee className="w-5 h-5 text-amber-400" />
            <span className="font-bold text-lg">""" + name + """</span>
          </div>
          <div className="flex gap-8 text-sm text-gray-500">
            <a href="#menu" className="hover:text-amber-400 transition-colors">Menu</a>
            <a href="#about" className="hover:text-amber-400 transition-colors">About</a>
            <a href="#reviews" className="hover:text-amber-400 transition-colors">Reviews</a>
            <a href="#visit" className="hover:text-amber-400 transition-colors">Visit</a>
          </div>
          <p className="text-gray-600 text-sm">© 2025 """ + name + """. Built with <span className="text-amber-400">Heaven AI</span></p>
        </div>
      </footer>
    </main>
  );
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# BUSINESS / DEFAULT
# ─────────────────────────────────────────────────────────────────────────────
def _business_page(name: str) -> str:
    return """'use client';

import { useState } from 'react';
import { Star, ChevronRight, Sparkles, Zap, Shield, Users, ArrowRight, Check, Globe, Award, TrendingUp } from 'lucide-react';

const features = [
  { icon: Sparkles, title: 'Premium Quality', desc: 'Every detail is crafted to perfection, ensuring an experience that exceeds expectations.' },
  { icon: Zap, title: 'Lightning Fast', desc: 'Optimized performance that keeps you moving at the speed of innovation.' },
  { icon: Shield, title: 'Enterprise Security', desc: 'Bank-grade encryption and security protocols to protect what matters most.' },
  { icon: Globe, title: 'Global Scale', desc: 'Built to handle millions of users across every continent seamlessly.' },
  { icon: Award, title: 'Award Winning', desc: 'Recognized by industry leaders for excellence in design and technology.' },
  { icon: TrendingUp, title: 'Growth Focused', desc: 'Data-driven insights and tools designed to accelerate your success.' },
];

const stats = [
  { value: '10K+', label: 'Active Users' },
  { value: '99.9%', label: 'Uptime' },
  { value: '4.9/5', label: 'Rating' },
  { value: '24/7', label: 'Support' },
];

const testimonials = [
  { name: 'Alex Chen', role: 'CEO, TechFlow', text: 'This transformed how we do business. Incredible results from day one.', avatar: '👨‍💻' },
  { name: 'Maria Santos', role: 'Director, Scale Inc', text: 'The best investment we made this year. Our team productivity doubled.', avatar: '👩‍💼' },
  { name: 'David Park', role: 'Founder, NextGen', text: 'Elegant, powerful, and reliable. Everything we needed and more.', avatar: '🧑‍🚀' },
];

const plans = [
  { name: 'Starter', price: 'Free', features: ['Up to 3 projects', 'Basic analytics', 'Community support', '1GB storage'], popular: false },
  { name: 'Pro', price: '$29', features: ['Unlimited projects', 'Advanced analytics', 'Priority support', '100GB storage', 'Custom domains', 'API access'], popular: true },
  { name: 'Enterprise', price: '$99', features: ['Everything in Pro', 'Dedicated manager', 'SLA guarantee', 'Unlimited storage', 'SSO & SAML', 'Custom integrations'], popular: false },
];

export default function Home() {
  const [annual, setAnnual] = useState(true);

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#0a0a0a] via-[#0d0d2b] to-[#0a0a0a] text-white">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 backdrop-blur-xl bg-black/40 border-b border-purple-900/20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
            ✨ """ + name + """
          </h1>
          <div className="hidden md:flex gap-8 text-sm text-gray-300">
            {['Features', 'Pricing', 'Reviews'].map(l => (
              <a key={l} href={`#${l.toLowerCase()}`} className="hover:text-purple-400 transition-colors">{l}</a>
            ))}
          </div>
          <a href="#pricing" className="bg-gradient-to-r from-purple-500 to-pink-600 px-5 py-2 rounded-full text-sm font-semibold hover:scale-105 hover:shadow-lg hover:shadow-purple-500/25 transition-all">
            Get Started
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-24 px-6 relative overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-purple-500/10 rounded-full blur-3xl" />
        <div className="max-w-7xl mx-auto relative z-10 text-center">
          <div className="inline-flex items-center gap-2 bg-purple-500/10 border border-purple-500/20 rounded-full px-4 py-1.5 text-purple-400 text-sm mb-6">
            <Sparkles className="w-4 h-4" /> Now available worldwide
          </div>
          <h2 className="text-6xl md:text-8xl font-black leading-[0.9] tracking-tight mb-6 max-w-4xl mx-auto">
            Build Something
            <span className="block bg-gradient-to-r from-purple-400 via-pink-400 to-orange-400 bg-clip-text text-transparent">
              Extraordinary
            </span>
          </h2>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            The all-in-one platform that empowers you to create, scale, and succeed — without the complexity.
          </p>
          <div className="flex flex-wrap justify-center gap-4 mb-16">
            <a href="#pricing" className="group bg-gradient-to-r from-purple-500 to-pink-600 px-8 py-4 rounded-full font-semibold text-lg hover:shadow-xl hover:shadow-purple-500/25 transition-all flex items-center gap-2">
              Start Free <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </a>
            <a href="#features" className="border border-gray-700 px-8 py-4 rounded-full font-semibold text-lg hover:bg-white/5 transition-all">
              Learn More
            </a>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 max-w-2xl mx-auto">
            {stats.map(s => (
              <div key={s.label} className="text-center">
                <div className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">{s.value}</div>
                <div className="text-xs text-gray-500 mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h3 className="text-4xl font-bold mb-4">Everything You Need</h3>
            <p className="text-gray-500 max-w-xl mx-auto">Powerful features designed to give you an unfair advantage</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f, i) => (
              <div key={i} className="group bg-white/[0.03] border border-white/[0.06] rounded-2xl p-8 hover:bg-white/[0.06] hover:border-purple-500/30 hover:scale-[1.02] transition-all duration-300">
                <div className="w-14 h-14 rounded-xl bg-purple-500/10 flex items-center justify-center mb-5 group-hover:bg-purple-500/20 transition-colors">
                  <f.icon className="w-7 h-7 text-purple-400" />
                </div>
                <h4 className="text-xl font-bold mb-3">{f.title}</h4>
                <p className="text-gray-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 px-6 bg-gradient-to-b from-transparent via-purple-950/10 to-transparent">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h3 className="text-4xl font-bold mb-4">Simple Pricing</h3>
            <div className="flex items-center justify-center gap-3 mt-6">
              <span className={`text-sm ${!annual ? 'text-white' : 'text-gray-500'}`}>Monthly</span>
              <button onClick={() => setAnnual(!annual)} className={`w-12 h-6 rounded-full relative transition-colors ${annual ? 'bg-purple-500' : 'bg-gray-700'}`}>
                <div className={`w-5 h-5 bg-white rounded-full absolute top-0.5 transition-all ${annual ? 'left-6' : 'left-0.5'}`} />
              </button>
              <span className={`text-sm ${annual ? 'text-white' : 'text-gray-500'}`}>Annual <span className="text-purple-400 text-xs">(-20%)</span></span>
            </div>
          </div>
          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {plans.map((plan, i) => (
              <div key={i} className={`rounded-2xl p-8 transition-all duration-300 hover:scale-[1.02] ${plan.popular ? 'bg-gradient-to-b from-purple-500/20 to-pink-500/10 border-2 border-purple-500/50 shadow-xl shadow-purple-500/10' : 'bg-white/[0.03] border border-white/[0.06]'}`}>
                {plan.popular && <div className="text-xs font-bold text-purple-400 mb-4 uppercase tracking-wider">Most Popular</div>}
                <h4 className="text-xl font-bold mb-1">{plan.name}</h4>
                <div className="flex items-baseline gap-1 mb-6">
                  <span className="text-4xl font-black">{plan.price}</span>
                  {plan.price !== 'Free' && <span className="text-gray-500 text-sm">/{annual ? 'year' : 'month'}</span>}
                </div>
                <ul className="space-y-3 mb-8">
                  {plan.features.map((f, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm text-gray-300">
                      <Check className="w-4 h-4 text-purple-400 shrink-0" /> {f}
                    </li>
                  ))}
                </ul>
                <button className={`w-full py-3 rounded-xl font-semibold transition-all hover:scale-[1.01] ${plan.popular ? 'bg-gradient-to-r from-purple-500 to-pink-600 hover:shadow-lg hover:shadow-purple-500/25' : 'bg-white/10 hover:bg-white/15'}`}>
                  {plan.price === 'Free' ? 'Start Free' : 'Get Started'}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section id="reviews" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <h3 className="text-4xl font-bold mb-12 text-center">Loved by Teams Everywhere</h3>
          <div className="grid md:grid-cols-3 gap-6">
            {testimonials.map((t, i) => (
              <div key={i} className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-8 hover:border-purple-500/20 transition-all duration-300">
                <div className="flex gap-1 mb-4">
                  {Array.from({ length: 5 }).map((_, j) => (
                    <Star key={j} className="w-4 h-4 fill-purple-400 text-purple-400" />
                  ))}
                </div>
                <p className="text-gray-300 mb-6 leading-relaxed">&ldquo;{t.text}&rdquo;</p>
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{t.avatar}</span>
                  <div>
                    <div className="font-semibold text-sm">{t.name}</div>
                    <div className="text-xs text-gray-500">{t.role}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6">
        <div className="max-w-4xl mx-auto text-center bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-3xl p-16">
          <h3 className="text-4xl font-bold mb-4">Ready to Get Started?</h3>
          <p className="text-gray-400 mb-8 max-w-xl mx-auto">Join thousands of teams already building something extraordinary.</p>
          <a href="#pricing" className="inline-flex items-center gap-2 bg-gradient-to-r from-purple-500 to-pink-600 px-8 py-4 rounded-full font-semibold text-lg hover:shadow-xl hover:shadow-purple-500/25 transition-all">
            Start Building <ArrowRight className="w-5 h-5" />
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] py-10 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
          <span className="font-bold text-lg">✨ """ + name + """</span>
          <div className="flex gap-8 text-sm text-gray-500">
            <a href="#features" className="hover:text-purple-400 transition-colors">Features</a>
            <a href="#pricing" className="hover:text-purple-400 transition-colors">Pricing</a>
            <a href="#reviews" className="hover:text-purple-400 transition-colors">Reviews</a>
          </div>
          <p className="text-gray-600 text-sm">© 2025 """ + name + """. Built with <span className="text-purple-400">Heaven AI</span></p>
        </div>
      </footer>
    </main>
  );
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Stubs for other types — use business page as base
# ─────────────────────────────────────────────────────────────────────────────
def _portfolio_page(name: str) -> str:
    return _business_page(name)

def _ecommerce_page(name: str) -> str:
    return _business_page(name)

def _saas_page(name: str) -> str:
    return _business_page(name)

def _fitness_page(name: str) -> str:
    return _business_page(name)

def _agency_page(name: str) -> str:
    return _business_page(name)

def _creative_page(name: str) -> str:
    return _business_page(name)

def _blog_page(name: str) -> str:
    return _business_page(name)
