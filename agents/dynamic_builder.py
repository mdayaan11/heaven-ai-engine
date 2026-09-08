"""
Heaven AI — Dynamic Page Builder
Gemini generates CONTENT DATA (menu items, colors, descriptions).
A hardcoded template renders the LAYOUT.
Result: Custom content + bulletproof structure.
"""
from __future__ import annotations
import json
import re
from typing import Any, Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Gemini content prompt — asks for DATA not CODE
# ─────────────────────────────────────────────────────────────────────────────
CONTENT_PROMPT = """You are a world-class brand strategist and content writer.

Given a project idea, generate CUSTOMIZED website content as JSON.
Analyze the idea carefully — extract the exact theme, cuisine, industry, brand personality.

RULES:
- "tagline" must be specific to the project (NOT generic like "Build Something")
- "description" must describe THIS specific business/project
- "menu_items" or "features" must be relevant to the actual business type
- "theme" colors must match the brand identity (warm golds for Indian food, deep greens for eco, etc.)
- All text must feel premium and professional
- If a person's name is mentioned, use it appropriately

Respond ONLY in valid JSON — no markdown:
{
  "brand_name": "Short brand name (2-4 words)",
  "tagline": "Catchy tagline specific to this project",
  "description": "2-sentence description of this specific business",
  "theme": {
    "primary": "tailwind color like amber-500 or emerald-500",
    "accent": "secondary color like orange-600 or teal-500",
    "gradient_from": "hex like #1a0f0a",
    "gradient_via": "hex like #0d1a0a",
    "gradient_to": "hex like #0a0a0a"
  },
  "stats": [
    {"value": "12+", "label": "Years"},
    {"value": "50k+", "label": "Guests"},
    {"value": "4.9", "label": "Rating"},
    {"value": "100+", "label": "Menu Items"}
  ],
  "items": [
    {"name": "Item Name", "price": "$12.00", "desc": "Description", "cat": "category1"},
    {"name": "Item 2", "price": "$15.00", "desc": "Description", "cat": "category2"}
  ],
  "categories": [
    {"key": "all", "label": "✨ All"},
    {"key": "category1", "label": "🍛 Category 1"},
    {"key": "category2", "label": "🥘 Category 2"}
  ],
  "features": [
    {"title": "Feature 1", "desc": "Why this business is special", "emoji": "🏆"},
    {"title": "Feature 2", "desc": "Another unique selling point", "emoji": "✨"},
    {"title": "Feature 3", "desc": "Third differentiator", "emoji": "🎯"}
  ],
  "reviews": [
    {"name": "Reviewer", "text": "Review text", "stars": 5, "avatar": "👩"},
    {"name": "Reviewer 2", "text": "Review text", "stars": 5, "avatar": "👨"}
  ],
  "contact": {
    "address": "Street address",
    "phone": "(555) 123-4567",
    "hours": [
      {"day": "Monday - Friday", "time": "11:00 AM - 10:00 PM"},
      {"day": "Saturday - Sunday", "time": "10:00 AM - 11:00 PM"}
    ]
  },
  "cta_button": "Reserve a Table",
  "form_title": "Make a Reservation",
  "form_success_emoji": "🎉",
  "form_success_text": "Reservation confirmed!"
}

Generate 6-8 menu items across 2-3 categories. Make EVERYTHING specific to the project idea."""


# ─────────────────────────────────────────────────────────────────────────────
# Default content when Gemini fails
# ─────────────────────────────────────────────────────────────────────────────
def default_content(project_name: str, idea: str) -> Dict[str, Any]:
    """Fallback content — still decent, but generic."""
    return {
        "brand_name": project_name,
        "tagline": "Where Quality Meets Excellence",
        "description": "A premium experience crafted with passion and attention to every detail.",
        "theme": {
            "primary": "purple-500",
            "accent": "pink-600",
            "gradient_from": "#0a0a0a",
            "gradient_via": "#0d0d2b",
            "gradient_to": "#0a0a0a",
        },
        "stats": [
            {"value": "10+", "label": "Years"},
            {"value": "50k+", "label": "Customers"},
            {"value": "4.9", "label": "Rating"},
            {"value": "24/7", "label": "Support"},
        ],
        "items": [],
        "categories": [],
        "features": [
            {"title": "Premium Quality", "desc": "Every detail crafted to perfection.", "emoji": "✨"},
            {"title": "Expert Team", "desc": "Passionate professionals at your service.", "emoji": "🏆"},
            {"title": "Customer First", "desc": "Your satisfaction is our priority.", "emoji": "💎"},
        ],
        "reviews": [
            {"name": "Alex M.", "text": "Absolutely incredible experience. Will definitely come back!", "stars": 5, "avatar": "👨‍💼"},
            {"name": "Sarah K.", "text": "The best in the city. Highly recommended to everyone.", "stars": 5, "avatar": "👩‍💻"},
            {"name": "David R.", "text": "Outstanding quality and service. 10/10!", "stars": 5, "avatar": "🧑‍🍳"},
        ],
        "contact": {
            "address": "123 Main Street, City Center",
            "phone": "(555) 123-4567",
            "hours": [
                {"day": "Monday - Friday", "time": "9:00 AM - 9:00 PM"},
                {"day": "Saturday - Sunday", "time": "10:00 AM - 10:00 PM"},
            ],
        },
        "cta_button": "Get Started",
        "form_title": "Get In Touch",
        "form_success_emoji": "🚀",
        "form_success_text": "Message sent! We'll get back to you soon.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Render functions — build actual TSX from content data
# ─────────────────────────────────────────────────────────────────────────────
def render_restaurant_page(c: Dict[str, Any]) -> str:
    """Render a restaurant/cafe/food page from content data."""
    name = c.get("brand_name", "Restaurant")
    tagline = c.get("tagline", "Authentic Dining Experience")
    desc = c.get("description", "A premium dining experience.")
    t = c.get("theme", {})
    pri = t.get("primary", "amber-500")
    acc = t.get("accent", "orange-600")
    g_from = t.get("gradient_from", "#1a0f0a")
    g_via = t.get("gradient_via", "#0d0d0d")
    g_to = t.get("gradient_to", "#0a0a0a")

    stats_jsx = ""
    for s in c.get("stats", []):
        stats_jsx += f"""
            <div className="text-center">
              <div className="text-3xl font-bold text-{pri}">{s['value']}</div>
              <div className="text-xs text-gray-500 mt-1">{s['label']}</div>
            </div>"""

    items_json = json.dumps(c.get("items", []))
    cats_json = json.dumps(c.get("categories", []))

    features_jsx = ""
    for f in c.get("features", []):
        features_jsx += f"""
              <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-8 hover:border-{pri}/30 hover:scale-[1.02] transition-all duration-300">
                <div className="text-4xl mb-4">{f['emoji']}</div>
                <h4 className="text-xl font-bold mb-3">{f['title']}</h4>
                <p className="text-gray-500 leading-relaxed">{f['desc']}</p>
              </div>"""

    reviews_jsx = ""
    for r in c.get("reviews", []):
        stars_jsx = "".join([f'<Star key={{{j}}} className="w-4 h-4 fill-{pri} text-{pri}" />' for j in range(r.get("stars", 5))])
        reviews_jsx += f"""
              <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 hover:border-{pri}/20 transition-all duration-300">
                <div className="flex gap-1 mb-3">{stars_jsx}</div>
                <p className="text-gray-300 mb-4 italic text-sm leading-relaxed">&ldquo;{r['text']}&rdquo;</p>
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{r['avatar']}</span>
                  <span className="text-sm text-{pri} font-semibold">{r['name']}</span>
                </div>
              </div>"""

    contact = c.get("contact", {})
    hours_jsx = ""
    for h in contact.get("hours", []):
        hours_jsx += f"""
                <div className="flex justify-between py-2 border-b border-white/[0.04] last:border-0">
                  <span className="text-gray-400">{h['day']}</span>
                  <span className="text-{pri} font-medium">{h['time']}</span>
                </div>"""

    cta = c.get("cta_button", "Reserve")
    form_title = c.get("form_title", "Get In Touch")
    form_emoji = c.get("form_success_emoji", "🎉")
    form_text = c.get("form_success_text", "Success!")

    return f"""'use client';

import {{ useState }} from 'react';
import {{ Star, ChevronRight, MapPin, Phone, Clock }} from 'lucide-react';

const menuItems: any[] = {items_json};
const categories: any[] = {cats_json};

export default function Home() {{
  const [tab, setTab] = useState('all');
  const filtered = tab === 'all' ? menuItems : menuItems.filter((i: any) => i.cat === tab);
  const [formSent, setFormSent] = useState(false);

  return (
    <main className="min-h-screen bg-gradient-to-br from-[{g_from}] via-[{g_via}] to-[{g_to}] text-white">
      {{/* Navbar */}}
      <nav className="fixed top-0 w-full z-50 backdrop-blur-xl bg-black/40 border-b border-{pri}/20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-{pri} to-{acc} bg-clip-text text-transparent">
            {name}
          </h1>
          <div className="hidden md:flex gap-8 text-sm text-gray-300">
            {{['Menu', 'About', 'Reviews', 'Visit'].map(link => (
              <a key={{link}} href={{`#${{link.toLowerCase()}}`}} className="hover:text-{pri} transition-colors duration-200">{{link}}</a>
            ))}}
          </div>
          <a href="#visit" className="bg-gradient-to-r from-{pri} to-{acc} px-5 py-2 rounded-full text-sm font-semibold hover:scale-105 hover:shadow-lg hover:shadow-{pri}/25 transition-all text-white">
            {cta}
          </a>
        </div>
      </nav>

      {{/* Hero */}}
      <section className="relative pt-32 pb-28 px-6 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-{pri}/15 via-transparent to-transparent" />
        <div className="absolute top-20 right-20 w-96 h-96 bg-{pri}/5 rounded-full blur-3xl" />
        <div className="max-w-7xl mx-auto relative z-10">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 bg-{pri}/10 border border-{pri}/20 rounded-full px-4 py-1.5 text-{pri} text-sm mb-6 animate-pulse">
              <Star className="w-4 h-4 fill-current" /> Authentic Experience
            </div>
            <h2 className="text-6xl md:text-8xl font-black leading-[0.9] tracking-tight mb-6">
              {tagline.split()[0] if tagline else 'Welcome'}
              <span className="block bg-gradient-to-r from-{pri} via-{acc} to-{pri} bg-clip-text text-transparent">
                {' '.join(tagline.split()[1:]) if tagline else 'to ' + name}
              </span>
            </h2>
            <p className="text-xl text-gray-400 max-w-xl mb-8 leading-relaxed">
              {desc}
            </p>
            <div className="flex flex-wrap gap-4">
              <a href="#menu" className="group bg-gradient-to-r from-{pri} to-{acc} px-8 py-3.5 rounded-full font-semibold text-lg hover:shadow-lg hover:shadow-{pri}/25 transition-all flex items-center gap-2 text-white">
                Explore Menu <ChevronRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </a>
              <a href="#visit" className="border border-gray-700 px-8 py-3.5 rounded-full font-semibold text-lg hover:bg-white/5 transition-all">
                Find Us
              </a>
            </div>
          </div>
          <div className="mt-16 grid grid-cols-4 gap-8 max-w-lg">
            {stats_jsx}
          </div>
        </div>
      </section>

      {{/* Menu */}}
      <section id="menu" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <h3 className="text-4xl font-bold mb-2">Our Menu</h3>
          <p className="text-gray-500 mb-8">Crafted with love, served with passion</p>
          <div className="flex gap-3 mb-10 flex-wrap">
            {{categories.map((c: any) => (
              <button key={{c.key}} onClick={{() => setTab(c.key)}}
                className={{`px-6 py-2.5 rounded-full text-sm font-medium transition-all duration-200 ${{tab === c.key ? 'bg-{pri} text-black shadow-lg shadow-{pri}/25' : 'bg-white/5 text-gray-400 hover:bg-white/10'}}`}}>
                {{c.label}}
              </button>
            ))}}
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5">
            {{filtered.map((item: any, i: number) => (
              <div key={{i}} className="group bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 hover:bg-white/[0.06] hover:border-{pri}/30 hover:scale-[1.02] transition-all duration-300 cursor-pointer">
                <div className="flex justify-between items-start mb-3">
                  <h4 className="text-lg font-semibold group-hover:text-{pri} transition-colors">{{item.name}}</h4>
                  <span className="text-{pri} font-bold text-lg">{{item.price}}</span>
                </div>
                <p className="text-gray-500 text-sm leading-relaxed">{{item.desc}}</p>
              </div>
            ))}}
          </div>
        </div>
      </section>

      {{/* About */}}
      <section id="about" className="py-24 px-6 bg-gradient-to-b from-transparent via-{pri}/5 to-transparent">
        <div className="max-w-7xl mx-auto">
          <h3 className="text-4xl font-bold mb-12 text-center">Why Choose Us</h3>
          <div className="grid md:grid-cols-3 gap-8">
            {features_jsx}
          </div>
        </div>
      </section>

      {{/* Reviews */}}
      <section id="reviews" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <h3 className="text-4xl font-bold mb-3">What Our Guests Say</h3>
          <p className="text-gray-500 mb-12">Join thousands of happy customers</p>
          <div className="grid md:grid-cols-3 gap-6">
            {reviews_jsx}
          </div>
        </div>
      </section>

      {{/* Contact */}}
      <section id="visit" className="py-24 px-6 bg-gradient-to-t from-{pri}/10 to-transparent">
        <div className="max-w-7xl mx-auto grid md:grid-cols-2 gap-12">
          <div>
            <h3 className="text-4xl font-bold mb-8">Visit Us</h3>
            <div className="space-y-4 text-gray-400 mb-8">
              <p className="flex items-center gap-3"><MapPin className="w-5 h-5 text-{pri} shrink-0" /> {contact.get('address', '123 Main St')}</p>
              <p className="flex items-center gap-3"><Phone className="w-5 h-5 text-{pri} shrink-0" /> {contact.get('phone', '(555) 123-4567')}</p>
            </div>
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6">
              <h4 className="font-bold mb-4 flex items-center gap-2"><Clock className="w-5 h-5 text-{pri}" /> Opening Hours</h4>
              {hours_jsx}
            </div>
          </div>
          <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-8">
            <h4 className="text-xl font-bold mb-6">{form_title}</h4>
            {{formSent ? (
              <div className="text-center py-12">
                <div className="text-5xl mb-4">{form_emoji}</div>
                <h5 className="text-xl font-bold text-{pri} mb-2">{form_text}</h5>
                <button onClick={{() => setFormSent(false)}} className="mt-4 text-sm text-{pri} underline">Make another</button>
              </div>
            ) : (
              <form className="space-y-4" onSubmit={{e => {{ e.preventDefault(); setFormSent(true); }}}}>
                <input type="text" placeholder="Your Name" required className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:border-{pri} focus:outline-none focus:ring-1 focus:ring-{pri}/50 transition-all" />
                <input type="email" placeholder="Email" required className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:border-{pri} focus:outline-none focus:ring-1 focus:ring-{pri}/50 transition-all" />
                <div className="grid grid-cols-2 gap-3">
                  <input type="date" required className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-{pri} focus:outline-none transition-all" />
                  <select className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-gray-400 focus:border-{pri} focus:outline-none transition-all">
                    <option>2 Guests</option><option>4 Guests</option><option>6 Guests</option><option>8+ Guests</option>
                  </select>
                </div>
                <button type="submit" className="w-full bg-gradient-to-r from-{pri} to-{acc} py-3.5 rounded-xl font-semibold hover:shadow-lg hover:shadow-{pri}/25 transition-all hover:scale-[1.01] text-white">
                  {cta} ✨
                </button>
              </form>
            )}}
          </div>
        </div>
      </section>

      {{/* Footer */}}
      <footer className="border-t border-white/[0.06] py-10 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
          <span className="font-bold text-lg bg-gradient-to-r from-{pri} to-{acc} bg-clip-text text-transparent">{name}</span>
          <div className="flex gap-8 text-sm text-gray-500">
            {{['Menu', 'About', 'Reviews', 'Visit'].map(l => (
              <a key={{l}} href={{`#${{l.toLowerCase()}}`}} className="hover:text-{pri} transition-colors">{{l}}</a>
            ))}}
          </div>
          <p className="text-gray-600 text-sm">© 2025 {name}. Built with <span className="text-{pri}">Heaven AI</span></p>
        </div>
      </footer>
    </main>
  );
}}
"""


def render_portfolio_page(c: Dict[str, Any]) -> str:
    """Render a portfolio page — delegates to page_templates for now."""
    from agents.page_templates import _portfolio_page
    return _portfolio_page(c.get("brand_name", "Portfolio"))


def render_business_page(c: Dict[str, Any]) -> str:
    """Render a business/SaaS page — delegates to page_templates for now."""
    from agents.page_templates import _business_page
    return _business_page(c.get("brand_name", "Business"))


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point — called from build_runner
# ─────────────────────────────────────────────────────────────────────────────
def build_dynamic_page(
    project_type: str,
    project_name: str,
    raw_idea: str,
    llm_call: Any = None,
) -> str:
    """Build a customized page.tsx using Gemini content + hardcoded layout.
    
    Args:
        project_type: 'cafe', 'portfolio', 'business', etc.
        project_name: Extracted brand name
        raw_idea: User's original prompt
        llm_call: Optional GeminiService._parse_json method
    """
    # 1. Try to get customized content from Gemini
    content = default_content(project_name, raw_idea)
    if llm_call:
        try:
            content = llm_call(
                CONTENT_PROMPT,
                f"Project idea: {raw_idea}\nExtracted brand name: {project_name}\nProject type: {project_type}",
                default_content(project_name, raw_idea),
            )
            # Ensure brand_name is correct
            if not content.get("brand_name") or len(content.get("brand_name", "")) > 30:
                content["brand_name"] = project_name
        except Exception:
            content = default_content(project_name, raw_idea)

    content["brand_name"] = content.get("brand_name", project_name) or project_name

    # 2. Render the page based on type
    if project_type in ("cafe", "restaurant", "food", "bakery"):
        return render_restaurant_page(content)
    elif project_type == "portfolio":
        return render_portfolio_page(content)
    else:
        return render_business_page(content)
