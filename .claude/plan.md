# Plan: Redesign OSINT Lookup Frontend with Modern UI

## Current State Analysis

**Current Tech Stack:**
- Streamlit (Python-based web framework)
- Custom CSS with dark theme
- Font: Sarabun (Thai) + Playfair Display
- Color scheme: Dark (#0B0E14) with gold accent (#C9A96E)
- Single-page app with form → timeline → report flow

**Current Features:**
1. Login with password protection
2. Search form (identifier type + value + context)
3. Real-time investigation timeline
4. Report display with Markdown
5. Graph visualization (relationship network)
6. Export: HTML (for PDF) and Markdown
7. Sidebar with tool descriptions and history

## Proposed New Design

### Technology Stack Decision

**Option 1: Keep Streamlit + Enhanced CSS/Components**
- Pros: Minimal migration, Python-native, existing logic intact
- Cons: Limited customization, hard to implement shadcn-ui (React-based)

**Option 2: Full Rewrite with Next.js + shadcn-ui + FastAPI Backend**
- Pros: Modern stack, full shadcn-ui access, smooth animations, better UX
- Cons: Complete rewrite, need API layer, more complex deployment

**Option 3: Hybrid - Streamlit Backend + Custom Frontend (iframe/components)**
- Pros: Keep existing logic, add modern UI gradually
- Cons: Complex integration, iframe limitations

**🎯 Recommended: Option 2 (Full Modern Stack)**

Rationale:
- shadcn-ui is React-based → requires JS framework
- Better animation support (Framer Motion)
- More control over UX flow
- Scalable architecture
- Modern development experience

### New Tech Stack

```
Frontend:
- Next.js 14 (App Router)
- TypeScript
- shadcn-ui components
- Tailwind CSS
- Framer Motion (animations)
- Lucide Icons
- React Query (data fetching)

Backend:
- FastAPI (Python) - expose existing osint_agent as API
- WebSocket for real-time updates
- Pydantic models for validation

Deployment:
- Frontend: Vercel / Netlify
- Backend: Docker container
```

## UI/UX Design

### Design Principles
1. **Intelligence Agency Aesthetic** - Professional, classified, high-tech
2. **Thai + English Support** - Seamless bilingual experience
3. **Real-time Feedback** - Live updates with smooth transitions
4. **Data Visualization** - Interactive graphs, timelines, cards
5. **Accessibility** - WCAG AA compliant

### Color Palette (Enhanced)

```
Primary: 
- Gold: #C9A96E (accent)
- Background: #0B0E14 (deepest)
- Surface: #151922 (cards)
- Border: #1E2430

Secondary:
- Text Primary: #F2F2F2
- Text Secondary: #8A93A6
- Success: #4CAF50
- Warning: #FFC107
- Danger: #F44336
- Info: #2196F3

Gradients:
- Gold gradient: linear-gradient(135deg, #C9A96E 0%, #8B7355 100%)
- Glow: radial-gradient(circle, rgba(201,169,110,0.1) 0%, transparent 70%)
```

### Typography

```
Headings: 
- English: Inter (modern sans-serif)
- Thai: Sarabun
- Accent: Playfair Display (serif)

Body:
- English: Inter
- Thai: Sarabun

Code/Mono:
- JetBrains Mono
```

### Page Structure

#### 1. **Landing Page** (/)
```
┌─────────────────────────────────────────┐
│ ◆ OSINT LOOKUP                    [EN|TH]│
│                                           │
│     [Animated Hero Section]              │
│     "Intelligence-Grade OSINT Platform"  │
│                                           │
│     [Start Investigation] [Learn More]   │
│                                           │
│   ┌──────┐ ┌──────┐ ┌──────┐            │
│   │Phone │ │Email │ │Social│  Features  │
│   └──────┘ └──────┘ └──────┘            │
└─────────────────────────────────────────┘
```

#### 2. **Dashboard** (/dashboard)
```
┌──────────────────────────────────────────────────────┐
│ Sidebar                 Main Area                     │
│ ┌─────────┐  ┌──────────────────────────────────┐  │
│ │ Tools   │  │ Quick Search (Command Bar)        │  │
│ │ • Phone │  │ [Type to search...]          ⌘K  │  │
│ │ • Email │  └──────────────────────────────────┘  │
│ │ • User  │                                          │
│ │         │  ┌────────────┬────────────┬────────┐  │
│ │History  │  │ Today  (3) │ Week  (12) │ Month  │  │
│ │ • 08:12 │  └────────────┴────────────┴────────┘  │
│ │ • 07:45 │                                          │
│ │         │  [Investigation Cards with hover anim] │
│ └─────────┘  ┌──────────────────────────────────┐  │
│              │ 🔍 0812345678                     │  │
│              │ Status: ✓ Complete  •  2 min ago │  │
│              │ [View Report] →                   │  │
│              └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

#### 3. **Investigation Page** (/investigate/[id])
```
┌──────────────────────────────────────────────────────────┐
│ ← Back to Dashboard              [Export] [Share] [•••]  │
│                                                            │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ 🎯 Investigation Target: 0812345678                   │ │
│ │ Type: Phone  •  Started: 14:32  •  Duration: 2m 34s  │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                            │
│ ┌─────────────────┐  ┌───────────────────────────────┐  │
│ │ Timeline        │  │ Live Report (Auto-scroll)     │  │
│ │                 │  │                               │  │
│ │ ✓ Phone Info    │  │ # Summary                     │  │
│ │ ⚙ WhatsApp      │  │ ...                           │  │
│ │ ⚙ Web Search    │  │                               │  │
│ │ ↳ Found 3 links │  │ ## Evidence                   │  │
│ │ ⌕ Sherlock      │  │ ...                           │  │
│ │ ⏳ Processing... │  │                               │  │
│ │                 │  │ [Smooth fade-in animations]   │  │
│ └─────────────────┘  └───────────────────────────────┘  │
│                                                            │
│ [Tabs: Report | Graph | Evidence | Timeline | Tools]     │
└──────────────────────────────────────────────────────────┘
```

#### 4. **Graph Visualization** (/investigate/[id]/graph)
```
┌──────────────────────────────────────────────────────┐
│ Relationship Network                     [Fullscreen] │
│ ┌──────────────────────────────────────────────────┐ │
│ │                                                   │ │
│ │     [Interactive Force-Directed Graph]           │ │
│ │                                                   │ │
│ │     • Nodes: Entities (phone, email, username)   │ │
│ │     • Edges: Relationships (confidence-based)    │ │
│ │     • Zoom, pan, click to explore                │ │
│ │     • Animated entrance                          │ │
│ │                                                   │ │
│ └──────────────────────────────────────────────────┘ │
│ Legend: ─ High  ┈ Medium  ··· Low                   │
└──────────────────────────────────────────────────────┘
```

## shadcn-ui Components to Use

### Core Components
- `Button` - All CTAs, with variants (default, ghost, outline)
- `Card` - Investigation cards, tool cards
- `Input` - Search fields, form inputs
- `Select` - Identifier type dropdown
- `Textarea` - Context input
- `Tabs` - Report/Graph/Evidence views
- `Badge` - Status indicators, chips
- `Dialog` - Modals for confirmations
- `Command` - Command palette (⌘K search)
- `Separator` - Visual dividers
- `ScrollArea` - Timeline, report scrolling
- `Skeleton` - Loading states

### Advanced Components
- `Accordion` - Collapsible tool descriptions
- `Toast` - Success/error notifications
- `Progress` - Investigation progress bar
- `Avatar` - User profile (if multi-user)
- `DropdownMenu` - Actions menu (•••)
- `Sheet` - Sliding sidebar on mobile
- `Tooltip` - Contextual help

## Animation Strategy (Framer Motion)

### Entrance Animations
```tsx
// Fade up on page load
const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 }
}

// Stagger children (timeline steps)
const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.1
    }
  }
}

// Scale in (cards)
const scaleIn = {
  initial: { opacity: 0, scale: 0.9 },
  animate: { opacity: 1, scale: 1 },
  transition: { duration: 0.3 }
}
```

### Interactive Animations
- **Hover**: Lift card (translateY: -4px) + shadow increase
- **Click**: Scale down (0.98) then bounce back
- **Loading**: Pulse skeleton, rotating spinner
- **Success**: Green checkmark with bounce
- **Error**: Red shake animation

### Page Transitions
- Route changes: Fade + slight slide
- Tab switches: Cross-fade
- Modal open/close: Scale + fade overlay

## Implementation Phases

### Phase 1: Project Setup (Week 1)
1. Initialize Next.js project with TypeScript
2. Install shadcn-ui components
3. Set up Tailwind with custom theme
4. Configure fonts and icons
5. Create base layout structure

### Phase 2: Backend API (Week 1-2)
1. Create FastAPI app structure
2. Extract osint_agent logic into API routes
3. Implement WebSocket for real-time updates
4. Add CORS, authentication middleware
5. Write Pydantic models for requests/responses

### Phase 3: Core Pages (Week 2-3)
1. Landing page with hero section
2. Login/authentication flow
3. Dashboard with search
4. Investigation page with timeline
5. Report rendering (Markdown to React)

### Phase 4: Advanced Features (Week 3-4)
1. Graph visualization (D3.js or Vis.js)
2. Command palette (⌘K search)
3. Export functionality (PDF, JSON)
4. History and saved searches
5. Tool descriptions and help

### Phase 5: Polish & Deploy (Week 4)
1. Add all animations
2. Responsive design (mobile/tablet)
3. Accessibility audit
4. Performance optimization
5. Deploy to production

## File Structure

```
osint-lookup-web/
├── frontend/                 # Next.js app
│   ├── app/
│   │   ├── (auth)/
│   │   │   └── login/
│   │   ├── dashboard/
│   │   ├── investigate/
│   │   │   └── [id]/
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── ui/              # shadcn-ui components
│   │   ├── investigation/   # Custom components
│   │   ├── layout/
│   │   └── shared/
│   ├── lib/
│   │   ├── api.ts           # API client
│   │   ├── hooks/           # React Query hooks
│   │   └── utils.ts
│   ├── styles/
│   │   └── globals.css
│   └── public/
│
├── backend/                 # FastAPI app
│   ├── api/
│   │   ├── routes/
│   │   │   ├── investigate.py
│   │   │   ├── tools.py
│   │   │   └── auth.py
│   │   ├── models.py
│   │   └── websocket.py
│   ├── osint_agent/         # Existing Python code
│   ├── main.py
│   └── requirements.txt
│
└── docker-compose.yml
```

## Key Decisions Needed

1. **Keep Streamlit or Full Rewrite?**
   - Recommend: Full rewrite for best shadcn-ui experience
   
2. **Real-time Updates Method?**
   - WebSocket vs Server-Sent Events vs Polling
   - Recommend: WebSocket for true bi-directional communication

3. **Graph Library?**
   - D3.js (full control) vs Vis.js (easier) vs Cytoscape.js
   - Recommend: Vis.js for balance of features and ease

4. **Authentication?**
   - Keep simple password or add JWT/OAuth?
   - Recommend: Start with password, plan for JWT upgrade

5. **Deployment Strategy?**
   - Separate frontend/backend or monorepo?
   - Recommend: Monorepo with Docker Compose for local, separate for production

## Success Criteria

- ✅ Modern, professional design matching intelligence agency aesthetic
- ✅ Smooth 60fps animations throughout
- ✅ Real-time investigation updates
- ✅ Fully responsive (mobile, tablet, desktop)
- ✅ Accessible (keyboard nav, screen readers)
- ✅ Fast initial load (<2s)
- ✅ All existing features preserved
- ✅ Easy to extend with new tools

## Questions for User

1. Do you want to keep the Streamlit version or do a complete rewrite?
2. Timeline expectations - is 4 weeks acceptable?
3. Should we prioritize mobile experience or desktop-first?
4. Any specific animations or interactions you've seen and liked?
5. Should we keep Thai as primary language or make it truly bilingual?
