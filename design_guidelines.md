{
  "concepto_elegido": {
    "nombre": "Documento oficial / Certificado institucional",
    "resumen_2_lineas": "Pantalla /login como certificado institucional: marco doble hairline, esquinas con ornamento minimo y sello oficial como ancla visual. Grid editorial estricto (12 columnas) con jerarquia tipografica clara para que nada se sienta 'tirado'."
  },
  "brand_attributes": ["institucional", "serio", "ministerial", "alta gerencia", "editorial"],
  "palette": {
    "navy": {
      "bg": "#0B1428",
      "panel": "#0F1A33",
      "navy_2": "#1B2A4A"
    },
    "gold": {
      "primary": "#C8A951",
      "soft": "#D4B871"
    },
    "teal_accent": "#1FA6A0",
    "text": {
      "on_navy": "rgba(255,255,255,0.92)",
      "muted": "rgba(255,255,255,0.60)",
      "faint": "rgba(255,255,255,0.45)"
    },
    "borders": {
      "hairline_gold": "rgba(200,169,81,0.22)",
      "hairline_white": "rgba(255,255,255,0.10)"
    },
    "focus_ring": "rgba(200,169,81,0.18)"
  },
  "typography": {
    "fonts": {
      "headings": "Spectral (serif)",
      "body": "IBM Plex Sans (sans-serif)"
    },
    "scale": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl (Spectral, bold, leading-[1.05])",
      "h2": "text-3xl sm:text-4xl (Spectral, bold)",
      "kicker": "text-[11px] uppercase tracking-[0.35em] font-semibold",
      "body": "text-base (mobile: text-sm) / md:text-lg para subtitulo",
      "meta": "text-xs uppercase tracking-[0.18em]"
    },
    "rules": [
      "El titulo 'La Ley de las 7 Semanas' aparece UNA sola vez (solo hero).",
      "Evitar duplicar el mismo string como eyebrow/kicker.",
      "Strings visibles en espanol latinoamericano sin tildes en codigo."
    ]
  },
  "layout": {
    "grid": {
      "desktop": "12 columnas: izquierda 7-8 cols editorial, derecha 4-5 cols formulario (sticky)",
      "tablet": "columna unica con marco visible; formulario debajo del masthead",
      "mobile": "orden vertical: masthead -> hero -> quote -> formulario -> camino compacto -> footer"
    },
    "certificate_shell": {
      "description": "Contenedor principal con doble borde hairline y esquinas ornamentales minimas.",
      "classes": "rounded-[28px] p-4 sm:p-6 lg:p-8 + borders absolutos"
    },
    "whitespace": "Usar 2-3x mas espacio: gaps 10-12, padding 6-8, separadores hairline."
  },
  "components": {
    "shadcn_ui": {
      "button": "/app/frontend/src/components/ui/button.jsx",
      "input": "/app/frontend/src/components/ui/input.jsx",
      "label": "/app/frontend/src/components/ui/label.jsx"
    },
    "icons": {
      "library": "lucide-react",
      "required": ["Cross (badge)", "Stamp (sello)", "Quote (cita)", "ArrowRight (camino)", "Eye/EyeOff (password)"]
    }
  },
  "motion_microinteractions": {
    "quote": "Mantener rotacion cada 5s; animacion existente .fade-in-quote.",
    "focus": "Inputs con focus ring dorado (sin transition: all).",
    "hover": "Links/botones: transition-colors; CTA: transition-[background-color,box-shadow].",
    "seal": "Sello con glow suave (blur) sin animacion agresiva."
  },
  "css_tokens_and_utilities": {
    "file": "/app/frontend/src/App.css",
    "added_classes": [".login-noise", ".login-dots", ".login-gold", ".login-input"],
    "notes": [
      "No usar gradientes saturados; solo halos radiales muy suaves (decorativos).",
      "No usar paneles blancos; todo sobre navy con transparencias controladas."
    ]
  },
  "testing": {
    "data_testid_rule": "Todo elemento interactivo o informativo clave debe tener data-testid (kebab-case).",
    "examples": [
      "data-testid=\"manual-oficial-badge\"",
      "data-testid=\"login-submit-button\"",
      "data-testid=\"toggle-auth-mode\"",
      "data-testid=\"login-quote-text\""
    ]
  },
  "image_urls": {
    "logo": {
      "description": "Logo circular iglesia (transparente) importado desde presentationData.",
      "source": "LOGO_IGLESIA (no cambiar)"
    },
    "background": {
      "description": "Sin imagen de fondo; navy uniforme con noise/dots CSS.",
      "source": "CSS (.login-noise, .login-dots)"
    }
  },
  "instructions_to_main_agent": [
    "Concepto obligatorio: certificado institucional. Mantener marco doble hairline y sello como ancla.",
    "Eliminar duplicaciones del titulo: 'La Ley de las 7 Semanas' solo en H1.",
    "Badge debe decir exactamente 'MANUAL OFICIAL' (uppercase) con icono Cross.",
    "No tocar logica de auth; solo capa visual.",
    "Mantener fondo navy uniforme (sin cards blancas).",
    "Respetar grid 12 columnas en desktop; no colocar elementos 'flotando'."
  ]
}

<General UI UX Design Guidelines>  
    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms
    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text
   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json

 **GRADIENT RESTRICTION RULE**
NEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc
NEVER use dark gradients for logo, testimonial, footer etc
NEVER let gradients cover more than 20% of the viewport.
NEVER apply gradients to text-heavy content or reading areas.
NEVER use gradients on small UI elements (<100px width).
NEVER stack multiple gradient layers in the same viewport.

**ENFORCEMENT RULE:**
    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors

**How and where to use:**
   • Section backgrounds (not content backgrounds)
   • Hero section header content. Eg: dark to light to dark color
   • Decorative overlays and accent elements only
   • Hero section with 2-3 mild color
   • Gradients creation can be done for any angle say horizontal, vertical or diagonal

- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**

</Font Guidelines>

- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. 
   
- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.

- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.
   
- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly
    Eg: - if it implies playful/energetic, choose a colorful scheme
           - if it implies monochrome/minimal, choose a black–white/neutral scheme

**Component Reuse:**
	- Prioritize using pre-existing components from src/components/ui when applicable
	- Create new components that match the style and conventions of existing components when needed
	- Examine existing components to understand the project's component patterns before creating new ones

**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component

**Best Practices:**
	- Use Shadcn/UI as the primary component library for consistency and accessibility
	- Import path: ./components/[component-name]

**Export Conventions:**
	- Components MUST use named exports (export const ComponentName = ...)
	- Pages MUST use default exports (export default function PageName() {...})

**Toasts:**
  - Use `sonner` for toasts"
  - Sonner component are located in `/app/src/components/ui/sonner.tsx`

Use 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.
</General UI UX Design Guidelines>
