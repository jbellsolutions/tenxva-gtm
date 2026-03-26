# The Copywriter Council
> A multi-agent system where each legendary copywriter lives as an AI agent with specialized sub-agents for their distinct areas of genius.

## Architecture

```
                    ┌─────────────────────┐
                    │   COUNCIL ROUTER    │
                    │  (Orchestrator)     │
                    │                     │
                    │ Analyzes the brief, │
                    │ selects the right   │
                    │ copywriter(s), and  │
                    │ routes to agents    │
                    └────────┬────────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
     ┌──────▼──────┐  ┌─────▼──────┐  ┌──────▼──────┐
     │  SCHWARTZ   │  │  ABRAHAM   │  │  KENNEDY    │  ... (18 agents)
     │  Agent      │  │  Agent     │  │  Agent      │
     └──────┬──────┘  └─────┬──────┘  └──────┬──────┘
            │               │                │
     ┌──────┴──────┐  ┌────┴─────┐   ┌──────┴──────┐
     │ Sub-agents  │  │Sub-agents│   │ Sub-agents  │
     │ (3-5 each)  │  │(3-5 each)│   │ (3-5 each)  │
     └─────────────┘  └──────────┘   └─────────────┘
```

## How It Works

### 1. Council Router (Orchestrator)
The router receives any copywriting brief and:
- Analyzes the market awareness level (Schwartz's 5 levels)
- Analyzes the market sophistication level (Schwartz's 5 stages)
- Identifies the content type needed (email, sales page, headline, etc.)
- Selects 1-3 copywriter agents best suited to the task
- Can run agents in parallel for A/B testing or combine their outputs

### 2. Copywriter Agents (18 total)
Each agent embodies a specific copywriter's voice, philosophy, and methodology. The agent has:
- **System prompt**: Built from the copywriter's style_traits, specialties, and philosophy
- **Knowledge base**: All indexed text content from that copywriter's folder
- **Sub-agents**: Specialized for different aspects of their work

### 3. Sub-agents (3-5 per copywriter)
Each copywriter agent delegates to sub-agents for specific tasks within their domain.

---

## Agent Roster

### EUGENE SCHWARTZ — The Market Awareness Master
**Role:** The foundation. Every brief should pass through Schwartz's awareness/sophistication framework first.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `schwartz.awareness` | Market awareness level diagnosis + headline matching | 5 Levels of Awareness framework |
| `schwartz.sophistication` | Market sophistication analysis + messaging strategy | 5 Levels of Sophistication framework |
| `schwartz.headlines` | Headline generation using Schwartz patterns | 127 Winning Headlines collection |
| `schwartz.research` | 4-step research framework + copy assembly | Masterfiles research framework, 33-min system |
| `schwartz.brilliance` | Picture words, sensory language, cognitive chunking | Brilliance Breakthrough analysis |

### JAY ABRAHAM — The Strategy of Preeminence
**Role:** Strategic positioning, leverage, and partnership thinking.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `abraham.preeminence` | Strategy of preeminence positioning | Vimeo talks 1-5 |
| `abraham.leverage` | Cross-industry leverage and growth strategies | Overdeliver bonus sessions |
| `abraham.partnerships` | Joint venture and strategic alliance copy | Training sessions |
| `abraham.reframe` | Reframing offers for maximum perceived value | How to Get From Where You Are sessions |
| `abraham.authority` | Authority-building and trusted advisor positioning | Full corpus |

### BRIAN KURTZ — The Relationship Builder
**Role:** Nurture sequences, authority building, insider stories, lifetime value.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `kurtz.nurture` | Long-term nurture and relationship sequences | Blog posts, emails |
| `kurtz.insider` | Industry insider stories and credibility | Four Pillars, Overdeliver chapters |
| `kurtz.partnerships` | Partnership-driven growth (learned from Schwartz) | Eugene is my Homeboy, Building Larger Mice |
| `kurtz.direct_mail` | Classic direct mail strategy and execution | Legacy collection |

### TODD BROWN — The Mechanism Master
**Role:** Funnel copy, mechanism reveals, E5 method, marketing education.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `brown.mechanisms` | Unique mechanism creation and reveal copy | Email corpus |
| `brown.funnels` | Funnel messaging and conversion sequences | Marketing education content |
| `brown.e5` | E5 method application | Training materials |
| `brown.launch` | Launch sequences and event-driven copy | Campaign examples |

### DAN KENNEDY — The No-BS Closer
**Role:** Hard-hitting sales letters, direct mail, info product launches.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `kennedy.sales_letters` | Long-form sales letters | Titans swipe collection (6 parts) |
| `kennedy.direct_mail` | Direct mail packages and response drivers | Swipe files |
| `kennedy.info_products` | Info product positioning and pricing | Training materials |
| `kennedy.contrarian` | Contrarian angles and pattern interrupts | Full corpus |

### ALEX HORMOZI — The Offer Architect
**Role:** Offer creation, value equations, scaling frameworks.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `hormozi.offers` | Irresistible offer construction | Email corpus |
| `hormozi.value` | Value equation optimization (dream outcome / time / effort / risk) | Frameworks |
| `hormozi.scaling` | Scaling language and growth messaging | Tactical emails |

### PERRY MARSHALL — The 80/20 Strategist
**Role:** Market selection, traffic strategy, simplification frameworks.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `marshall.8020` | 80/20 analysis and market selection | Titans sessions 1-6 |
| `marshall.traffic` | Traffic strategy and Google Ads copy | Training materials |
| `marshall.simplification` | Business simplification frameworks | Full corpus |

### GARY BENCIVENGA — The Headline Craftsman
**Role:** Precision headline writing, control-beating copy.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `bencivenga.headlines` | Headline craft and testing frameworks | Marketing Bullets collection |
| `bencivenga.controls` | Control-beating strategies | Swipe analysis |
| `bencivenga.proof` | Proof and credibility elements | Full corpus |

### JOE SUGARMAN — The Story Seller
**Role:** Product storytelling, curiosity-driven long copy.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `sugarman.storytelling` | Product origin stories and narrative copy | Titans interview |
| `sugarman.curiosity` | Curiosity hooks and slippery slope copy | Ad examples |
| `sugarman.print` | Print ad construction | Full corpus |

### BILL MUELLER — The Story Sales Machine
**Role:** Story-led email sequences, curiosity hooks.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `mueller.story_emails` | Story-driven email sequences | Story Sales Machine emails |
| `mueller.curiosity` | Curiosity-first subject lines and hooks | Email corpus |
| `mueller.critiques` | Email copy critiques and rewrites | Training material |

### JON BUCHAN — The Charm Offensive
**Role:** Cold email, personality-driven outreach, humor.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `buchan.cold_email` | Personality-rich cold outreach | Email corpus |
| `buchan.humor` | Humor and pattern interrupts in B2B | Outreach examples |
| `buchan.charm` | Charm-based relationship building | Full corpus |

### LEAD GEN JAY — The Outbound Operator
**Role:** Lead generation, cold email systems, B2B prospecting.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `leggenjay.systems` | Lead gen system design | Email corpus |
| `leggenjay.prospecting` | Prospecting sequences and follow-ups | Tactical content |
| `leggenjay.b2b` | B2B outbound messaging | Full corpus |

### LIAM OTTLEY — The AI Agency Builder
**Role:** AI offers, automation angles, modern agency positioning.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `ottley.ai_offers` | AI service offer positioning | Email corpus |
| `ottley.automation` | Automation-as-value messaging | Content |
| `ottley.agency` | Agency scaling and positioning | Full corpus |

### TOM BILYEU — The Belief Shifter
**Role:** Mindset content, belief shifts, inspirational angles.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `bilyeu.mindset` | Mindset shifts and transformation copy | Email corpus |
| `bilyeu.inspiration` | Inspirational hooks and identity-based copy | Content |
| `bilyeu.impact` | Impact-driven positioning | Full corpus |

### KEN MCCARTHY — The Internet Pioneer
**Role:** Internet marketing fundamentals, online direct response.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `mccarthy.fundamentals` | Internet marketing fundamentals | Titans talk |
| `mccarthy.history` | DR history applied to modern channels | Full corpus |

### FRED CATONA — The Broadcast Specialist
**Role:** Radio and broadcast direct response.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `catona.radio` | Radio ad copy and scripts | Titans talk |
| `catona.media` | Media buying strategy | Full corpus |

### GREG RENKER — The Infomercial King
**Role:** Television direct response, celebrity-driven campaigns.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `renker.tv` | TV direct response and infomercial strategy | Titans talk |
| `renker.celebrity` | Celebrity endorsement campaigns | Full corpus |

### GORDON GROSSMAN — The List Master
**Role:** Subscription marketing, direct mail packages, list strategy.

| Sub-Agent | Specialty | Source Material |
|-----------|-----------|----------------|
| `grossman.subscription` | Subscription and renewal copy | Confessions of a Direct Mail Guy |
| `grossman.lists` | List strategy and segmentation | Full corpus |

---

## Council Workflows

### Workflow 1: Full Sales Page
```
Brief → Router → schwartz.awareness (diagnose level)
                → schwartz.sophistication (diagnose stage)
                → Router selects 2-3 agents based on diagnosis
                → Agent 1: Headlines (schwartz.headlines or bencivenga.headlines)
                → Agent 2: Body copy (kennedy.sales_letters or sugarman.storytelling)
                → Agent 3: Offer section (hormozi.offers or brown.mechanisms)
                → Router assembles final output
```

### Workflow 2: Cold Email Sequence
```
Brief → Router → buchan.cold_email (personality-driven opener)
               → leggenjay.systems (follow-up sequence)
               → mueller.story_emails (story-based nurture)
               → Router creates 5-7 email sequence blending styles
```

### Workflow 3: Launch Sequence
```
Brief → Router → brown.launch (launch framework)
               → abraham.reframe (value positioning)
               → kurtz.nurture (relationship warmup)
               → hormozi.offers (offer construction)
               → schwartz.headlines (headline options)
               → Router assembles launch email sequence
```

### Workflow 4: Content Repurposing
```
Brief → Router → abraham.authority (strategic positioning)
               → bilyeu.mindset (belief-shift angles)
               → ottley.ai_offers (modern tech angles)
               → Router creates multi-format content plan
```

### Workflow 5: Market Analysis
```
Brief → Router → schwartz.awareness (awareness audit)
               → schwartz.sophistication (sophistication audit)
               → marshall.8020 (market selection)
               → abraham.leverage (opportunity mapping)
               → Router produces market analysis report
```

---

## Implementation

Each agent is defined in `council/agents/{author_key}.json` with:
```json
{
  "agent_key": "eugene_schwartz",
  "display_name": "Eugene Schwartz",
  "role": "The Market Awareness Master",
  "system_prompt": "You are Eugene Schwartz...",
  "knowledge_sources": ["swipe-library imports path"],
  "sub_agents": [...],
  "best_for": [...],
  "style_traits": [...],
  "activation_triggers": [
    "market awareness", "headline", "sophistication",
    "desire stages", "long-form sales copy"
  ]
}
```

The router uses `activation_triggers` + the brief analysis to select agents. Multiple agents can run in parallel for A/B testing.
