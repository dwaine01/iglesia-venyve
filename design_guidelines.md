{
  "brand_attributes": {
    "tone": ["corporativo", "serio", "confiable", "sobrio", "premium"],
    "visual_personality": "Manual digital tipo plataforma de capacitación corporativa (no estilo ‘iglesia juvenil’). Mucho aire, tipografía editorial para títulos, UI limpia para lectura extensa.",
    "do_not": [
      "No usar estilos juguetones, stickers, ilustraciones infantiles.",
      "No usar morado.",
      "No usar gradientes oscuros/saturados ni cubrir más del 20% del viewport con gradientes.",
      "No centrar todo el contenido; mantener lectura en F-pattern (alineación izquierda)."
    ]
  },

  "information_architecture": {
    "primary_nav": {
      "pattern": "Sidebar colapsable + topbar",
      "items_es": [
        "Dashboard",
        "Introducción",
        "Mapa 7 Semanas",
        "Semanas (1–7)",
        "Registro de Contactos",
        "Estadísticas"
      ],
      "mobile": "Bottom sheet (Sheet) para navegación + breadcrumbs en páginas internas"
    },
    "page_templates": {
      "auth": "Pantalla limpia con panel izquierdo de marca + panel derecho con formulario.",
      "dashboard": "Bento grid: progreso general grande + tarjetas de métricas + accesos rápidos + actividad reciente.",
      "reading_page": "Layout de lectura: encabezado + tabla de contenidos lateral (ScrollArea) + contenido principal con tipografía cómoda.",
      "map": "Lienzo central con imagen/infografía + hotspots/capas + panel lateral de detalles.",
      "registry": "Tabla con filtros + drawer para detalle/edición.",
      "stats": "KPIs + gráficos (Recharts) + filtros por fecha/semana + exportación."
    }
  },

  "typography": {
    "google_fonts": {
      "heading": {
        "family": "Spectral",
        "weights": [400, 600, 700],
        "usage": "Títulos del manual, encabezados de secciones, nombres de semanas. Sensación editorial/seria."
      },
      "body": {
        "family": "IBM Plex Sans",
        "weights": [400, 500, 600],
        "usage": "UI, párrafos largos, tablas, formularios. Excelente legibilidad corporativa."
      },
      "mono_optional": {
        "family": "IBM Plex Mono",
        "weights": [400, 500],
        "usage": "IDs, códigos internos, etiquetas técnicas (opcional)."
      }
    },
    "tailwind_mapping": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
      "h2": "text-base md:text-lg font-medium text-muted-foreground",
      "section_title": "text-xl md:text-2xl font-semibold",
      "body": "text-sm md:text-base leading-7",
      "small": "text-xs md:text-sm text-muted-foreground"
    },
    "reading_rules": {
      "max_width": "max-w-[72ch] para contenido principal",
      "line_height": "leading-7 (body), leading-8 en bloques densos",
      "spacing": "Separación generosa: space-y-6 en secciones; headings con mt-10 mb-3"
    }
  },

  "color_system": {
    "notes": "Base navy + gold (marca infografía) con neutros cálidos para lectura. Teal solo como acento funcional (links/estados).",
    "palette_hex": {
      "navy_900": "#1B2A4A",
      "navy_950": "#0F1A33",
      "gold_500": "#C8A951",
      "gold_300": "#E2CF8A",
      "teal_500": "#1FA6A0",
      "teal_300": "#7ED7D2",
      "paper": "#FBFAF7",
      "stone_100": "#F3F1EA",
      "stone_200": "#E7E2D6",
      "ink": "#101828",
      "muted": "#667085",
      "success": "#1F7A5A",
      "warning": "#B7791F",
      "danger": "#B42318"
    },
    "css_tokens_hsl_for_shadcn": {
      "instruction": "Actualizar /app/frontend/src/index.css :root con estos HSL para que shadcn herede el tema.",
      "light": {
        "--background": "40 33% 98%",
        "--foreground": "222 47% 11%",
        "--card": "40 33% 99%",
        "--card-foreground": "222 47% 11%",
        "--popover": "40 33% 99%",
        "--popover-foreground": "222 47% 11%",
        "--primary": "221 46% 20%",
        "--primary-foreground": "40 33% 98%",
        "--secondary": "40 20% 93%",
        "--secondary-foreground": "221 46% 20%",
        "--muted": "40 18% 92%",
        "--muted-foreground": "215 16% 35%",
        "--accent": "43 52% 55%",
        "--accent-foreground": "221 46% 16%",
        "--border": "40 14% 86%",
        "--input": "40 14% 86%",
        "--ring": "43 52% 55%",
        "--destructive": "0 72% 45%",
        "--destructive-foreground": "40 33% 98%",
        "--radius": "0.75rem",
        "--chart-1": "221 46% 20%",
        "--chart-2": "43 52% 55%",
        "--chart-3": "186 55% 38%",
        "--chart-4": "215 16% 35%",
        "--chart-5": "40 18% 92%"
      },
      "dark_optional": {
        "note": "Modo oscuro opcional para líderes que trabajan de noche. Mantener sólido (sin gradientes).",
        "--background": "221 46% 10%",
        "--foreground": "40 33% 96%",
        "--card": "221 46% 12%",
        "--card-foreground": "40 33% 96%",
        "--primary": "43 52% 55%",
        "--primary-foreground": "221 46% 12%",
        "--secondary": "221 30% 18%",
        "--secondary-foreground": "40 33% 96%",
        "--muted": "221 30% 18%",
        "--muted-foreground": "40 10% 75%",
        "--accent": "186 55% 38%",
        "--accent-foreground": "221 46% 12%",
        "--border": "221 30% 22%",
        "--input": "221 30% 22%",
        "--ring": "43 52% 55%"
      }
    },
    "gradient_policy": {
      "allowed": [
        "Solo en fondos decorativos de hero/encabezados (máx 20% viewport).",
        "Overlays sutiles detrás del logo o en cabecera del login.",
        "Nunca en tarjetas de lectura ni tablas."
      ],
      "safe_gradients": [
        {
          "name": "Navy-to-paper header wash",
          "css": "bg-[radial-gradient(1200px_circle_at_20%_0%,rgba(200,169,81,0.18),transparent_55%),radial-gradient(900px_circle_at_80%_10%,rgba(31,166,160,0.12),transparent_50%),linear-gradient(180deg,#0F1A33_0%,#1B2A4A_55%,#FBFAF7_100%)]"
        }
      ]
    }
  },

  "layout_and_grid": {
    "app_shell": {
      "desktop": "Sidebar fijo (w-64) + contenido con max-w y padding generoso.",
      "tablet": "Sidebar colapsable (Sheet/Drawer).",
      "mobile": "Topbar compacta + navegación en Sheet; contenido a 1 columna."
    },
    "grid": {
      "dashboard": "grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6",
      "bento_spans": {
        "hero_tile": "lg:col-span-7",
        "kpi_stack": "lg:col-span-5",
        "map_preview": "lg:col-span-8",
        "activity": "lg:col-span-4"
      }
    },
    "spacing_tokens": {
      "section_padding": "px-4 sm:px-6 lg:px-8 py-6 lg:py-10",
      "card_padding": "p-4 sm:p-5",
      "content_gap": "space-y-6"
    }
  },

  "components": {
    "component_path": {
      "shadcn_primary": "/app/frontend/src/components/ui/",
      "use_components": [
        "button.jsx",
        "card.jsx",
        "input.jsx",
        "label.jsx",
        "checkbox.jsx",
        "progress.jsx",
        "tabs.jsx",
        "table.jsx",
        "badge.jsx",
        "breadcrumb.jsx",
        "separator.jsx",
        "scroll-area.jsx",
        "sheet.jsx",
        "drawer.jsx",
        "dialog.jsx",
        "dropdown-menu.jsx",
        "select.jsx",
        "textarea.jsx",
        "calendar.jsx",
        "sonner.jsx"
      ]
    },
    "patterns": {
      "topbar": {
        "elements": ["Breadcrumb", "Search (Command opcional)", "Perfil (DropdownMenu)", "CTA: Registrar contacto"],
        "classes": "sticky top-0 z-40 bg-background/80 backdrop-blur border-b"
      },
      "sidebar": {
        "classes": "bg-card border-r",
        "active_item": "bg-secondary text-foreground font-medium",
        "icon_style": "lucide-react icons, size-4/5, color muted"
      },
      "kpi_card": {
        "structure": "Card > header (label + badge) > big number > mini trend",
        "number_style": "text-2xl md:text-3xl font-semibold text-[color:var(--kpi-ink)]",
        "accent_rule": "Borde superior 2px en gold para tarjetas clave: border-t-2 border-t-[hsl(var(--accent))]"
      },
      "reading_card": {
        "use": "Introducción y semanas",
        "classes": "bg-card border shadow-sm rounded-xl",
        "inside": "prose-like spacing (pero sin plugin): space-y-4, leading-7"
      },
      "checklist": {
        "use": "Checklist por semana",
        "components": ["Checkbox", "Progress", "Badge"],
        "interaction": "Al marcar, animar progreso (Framer Motion opcional) y toast de confirmación (Sonner)."
      },
      "registry_table": {
        "components": ["Table", "Input", "Select", "DropdownMenu", "Drawer"],
        "row_hover": "hover:bg-secondary/60",
        "empty_state": "Card con icono + texto + botón 'Registrar primer contacto'"
      },
      "map_infographic": {
        "structure": "Imagen/infografía en AspectRatio + hotspots (botones transparentes) + panel lateral con Tabs",
        "hotspot": "Button variant=ghost con ring visible al focus; tooltip en hover",
        "note": "Mantener la infografía como imagen provista; encima colocar capas interactivas (posicionamiento absoluto)."
      }
    },
    "buttons": {
      "style": "Luxury / Elegant",
      "variants": {
        "primary": "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:bg-[hsl(var(--primary))]/90",
        "secondary": "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        "ghost": "hover:bg-secondary/70",
        "danger": "bg-[hsl(var(--destructive))] text-[hsl(var(--destructive-foreground))] hover:bg-[hsl(var(--destructive))]/90"
      },
      "motion": "hover:translate-y-[-1px] active:translate-y-0 active:scale-[0.99] transition-colors duration-200"
    },
    "forms": {
      "inputs": "Input con focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]",
      "validation": "Mensajes en rojo (danger) debajo del campo; no usar solo color: incluir texto claro en español.",
      "testids": [
        "login-email-input",
        "login-password-input",
        "login-submit-button",
        "registry-search-input",
        "registry-add-contact-button"
      ]
    }
  },

  "motion_and_microinteractions": {
    "principles": [
      "Micro-animaciones discretas (corporativas): 120–180ms.",
      "Animar opacidad/translate en entradas de tarjetas; evitar rebotes.",
      "Hover con elevación mínima (shadow-sm -> shadow-md) y borde sutil."
    ],
    "recommended_library": {
      "name": "framer-motion",
      "install": "npm i framer-motion",
      "usage": "Animar aparición de tiles del dashboard y progreso de checklist."
    },
    "examples": {
      "card_enter": "initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{duration:0.18,ease:'easeOut'}}",
      "progress_smooth": "Animar value con motion + requestAnimationFrame o framer-motion"
    }
  },

  "data_visualization": {
    "library": {
      "name": "recharts",
      "install": "npm i recharts",
      "charts": ["LineChart (tendencia semanal)", "BarChart (contactos por semana)", "PieChart (estado de progreso)"]
    },
    "chart_styling": {
      "colors": {
        "primary_line": "#1B2A4A",
        "accent_bar": "#C8A951",
        "teal_highlight": "#1FA6A0",
        "grid": "#E7E2D6"
      },
      "empty_state": "Mostrar Skeleton + texto 'Aún no hay datos suficientes para mostrar estadísticas.'"
    }
  },

  "accessibility": {
    "wcag": "AA",
    "focus": "Siempre visible: focus-visible:ring-2 ring gold (accent) + ring-offset-2",
    "touch_targets": "min-h-[44px] en botones principales en móvil",
    "contrast": "Texto navy/ink sobre paper; evitar gold como texto principal en párrafos (solo acentos).",
    "reduced_motion": "Respetar prefers-reduced-motion: desactivar animaciones de entrada si aplica."
  },

  "content_style_spanish": {
    "voice": "Formal, claro, pastoral pero corporativo.",
    "labels": {
      "cta_primary": ["Continuar", "Guardar", "Registrar"],
      "cta_secondary": ["Ver detalles", "Editar", "Exportar"],
      "status": ["Completado", "En progreso", "Pendiente"]
    },
    "week_naming": [
      "Semana 1 — Preparación / Oración Profética",
      "Semana 2 — Invasión (NPT)",
      "Semana 3 — MCD",
      "Semana 4 — Liberación (LBS 1)",
      "Semana 5 — Bendición (LBS 2)",
      "Semana 6 — Sanidad (LBS 3)",
      "Semana 7 — Retiro + Cierre"
    ]
  },

  "image_urls": {
    "brand_backgrounds": [
      {
        "category": "login-left-panel",
        "description": "Textura abstracta navy/gold muy sobria para panel de marca (usar overlay oscuro para legibilidad).",
        "url": "https://images.unsplash.com/photo-1646315026053-27cf64144dd8?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85"
      },
      {
        "category": "dashboard-header-subtle",
        "description": "Fondo abstracto suave para encabezado del dashboard (usar como background-image con opacidad baja).",
        "url": "https://images.unsplash.com/photo-1646228148984-6d9de4b6edb2?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85"
      }
    ],
    "leadership_photos": [
      {
        "category": "introduction-hero",
        "description": "Foto profesional de reunión/liderazgo (evitar estética corporativa fría; usar recorte cálido).",
        "url": "https://images.unsplash.com/photo-1714974528796-e4e7a077d0cc?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85"
      }
    ],
    "infographic_assets": [
      {
        "category": "map-main",
        "description": "Usar la(s) imagen(es) provistas por la iglesia para el mapa/infografía de 7 semanas. No reemplazar.",
        "url": "PROVIDED_BY_USER"
      },
      {
        "category": "church-logo",
        "description": "Logo oficial 'Casa de Oración Ven y Ve' (verde/cian sobre negro). Debe aparecer en login, sidebar y footer.",
        "url": "PROVIDED_BY_USER"
      }
    ]
  },

  "implementation_notes_js": {
    "react_files": "El proyecto usa .js (no .tsx). Mantener componentes en JS con prop-types opcional.",
    "icons": {
      "library": "lucide-react",
      "usage": "import { LayoutDashboard, Map, BookOpen, Users, BarChart3, LogOut } from 'lucide-react'"
    },
    "testids_rule": "Agregar data-testid a TODO elemento interactivo y a KPIs/valores críticos (ej: data-testid='dashboard-total-contactos-value').",
    "suggested_testids": {
      "sidebar": [
        "sidebar-nav-dashboard",
        "sidebar-nav-introduccion",
        "sidebar-nav-mapa",
        "sidebar-nav-semanas",
        "sidebar-nav-registro",
        "sidebar-nav-estadisticas"
      ],
      "dashboard": [
        "dashboard-progress-overview-card",
        "dashboard-weekly-progress-bar",
        "dashboard-quick-add-contact-button"
      ],
      "map": [
        "map-week-hotspot-1",
        "map-week-hotspot-2",
        "map-week-hotspot-3",
        "map-week-hotspot-4",
        "map-week-hotspot-5",
        "map-week-hotspot-6",
        "map-week-hotspot-7"
      ]
    }
  },

  "instructions_to_main_agent": [
    "Actualizar tokens de color en /app/frontend/src/index.css para reflejar navy/gold/paper (ver css_tokens_hsl_for_shadcn).",
    "Eliminar estilos default de CRA en /app/frontend/src/App.css (App-header centrado, etc.) y reemplazar por estilos mínimos o dejarlo vacío.",
    "Implementar App Shell: Sidebar + Topbar sticky con Breadcrumb y acciones.",
    "Dashboard: usar bento grid (12 cols) con Card/Progress/Badge; incluir KPIs y accesos rápidos.",
    "Páginas de semanas e Introducción: layout de lectura con max-w-[72ch], ScrollArea para índice lateral, y checklists por sección.",
    "Mapa/Infografía: renderizar imagen provista + hotspots (Buttons ghost) posicionados; panel lateral con Tabs para detalle y checklist.",
    "Registro de contactos: Table con filtros; Drawer para crear/editar; Sonner para confirmaciones.",
    "Estadísticas: Recharts con colores de marca; filtros por fecha (Calendar) y por semana (Select).",
    "Asegurar data-testid en todos los elementos interactivos y valores críticos.",
    "Todo el contenido y labels en español."
  ],

  "general_ui_ux_design_guidelines_appendix": "<General UI UX Design Guidelines>\n    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.\n</General UI UX Design Guidelines>"
}
