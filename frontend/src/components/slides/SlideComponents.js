import React from 'react';
import { motion } from 'framer-motion';
import {
  Sparkles, Church, Crown, Eye, Target, Heart, Users, Rocket, Shield, Flame,
  BookOpen, HandHeart, DoorOpen, Mountain, Home as HouseIcon, Megaphone,
  Wallet, Calendar, Star, CheckCircle2, Zap, GraduationCap, Award, ArrowRight, Compass
} from 'lucide-react';
import { LAS_9_PUERTAS, LAS_7_SEMANAS, IMAGEN_LEY_7_SEMANAS, LOGO_IGLESIA } from '../../data/presentationData';

const ICON_MAP = {
  HandHeart, DoorOpen, Heart, Mountain, BookOpen, HouseIcon, Megaphone, Wallet, Calendar,
};

// ============================================================
// SLIDE: PORTADA
// ============================================================
export const SlidePortada = ({ slide }) => (
  <div className="flex flex-col items-center justify-center min-h-full text-center px-6 py-10 bg-gradient-to-br from-[#0F1A33] via-[#1B2A4A] to-[#2A3D63] text-white relative overflow-hidden">
    <div className="absolute inset-0 opacity-10" style={{
      backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(200,169,81,0.4) 1px, transparent 0)',
      backgroundSize: '32px 32px'
    }} />
    <div className="absolute top-0 right-0 w-96 h-96 bg-[#C8A951]/10 rounded-full blur-3xl -translate-y-24 translate-x-24" />
    <div className="absolute bottom-0 left-0 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl translate-y-24 -translate-x-24" />

    <motion.div
      initial={{ scale: 0, rotate: -180 }}
      animate={{ scale: 1, rotate: 0 }}
      transition={{ type: 'spring', duration: 1 }}
      className="relative w-32 h-32 sm:w-44 sm:h-44 rounded-full bg-[#0F1A33] flex items-center justify-center mb-6 shadow-2xl p-4 border-4 border-[#C8A951]/30"
    >
      <img
        src={LOGO_IGLESIA}
        alt="Casa de Oración Ven y Ve"
        className="w-full h-full object-contain logo-transparent"
      />
    </motion.div>

    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="relative z-10">
      <div className="inline-flex items-center gap-1.5 bg-[#C8A951]/20 border border-[#C8A951]/40 text-[#C8A951] text-xs font-semibold uppercase tracking-widest rounded-full px-3 py-1 mb-4">
        <Sparkles className="w-3 h-3" /> Manual Oficial
      </div>
      <h1 className="text-4xl sm:text-6xl lg:text-7xl font-bold mb-3 leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
        <span className="text-[#C8A951]">La Ley</span> de las<br />
        <span className="italic">7 Semanas</span>
      </h1>
      <div className="w-32 h-0.5 bg-[#C8A951] mx-auto my-5" />
      <p className="text-lg sm:text-2xl text-white/80 mb-3 italic" style={{ fontFamily: 'Spectral, serif' }}>
        {slide.subtitle}
      </p>
      <p className="text-sm sm:text-base text-white/50 max-w-2xl mx-auto leading-relaxed">
        {slide.description}
      </p>
    </motion.div>
  </div>
);

// ============================================================
// SLIDE: IDENTIDAD (Visión, Misión, Valores)
// ============================================================
export const SlideIdentidad = () => {
  const cards = [
    { icon: Eye, label: 'Visión', text: 'Levantar discípulos que se conviertan en líderes, a través de un sistema intencional que transforma vidas y se multiplica.', color: 'from-purple-600 to-indigo-700' },
    { icon: Target, label: 'Misión', text: 'Evangelizar, consolidar, discipular y enviar personas, a través de un sistema de puertas ministeriales.', color: 'from-[#1FA6A0] to-teal-600' },
  ];
  const valores = ['Presencia de Dios', 'Amor por las almas', 'Relaciones intencionales', 'Formación continua', 'Multiplicación', 'Orden', 'Excelencia'];
  return (
    <div className="min-h-full px-6 py-10 bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
      <div className="max-w-5xl mx-auto w-full space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
          <h2 className="text-3xl sm:text-5xl font-bold text-[#1B2A4A] mb-2" style={{ fontFamily: 'Spectral, serif' }}>
            Nuestra Identidad
          </h2>
          <p className="text-muted-foreground text-sm sm:text-base">Visión · Misión · Valores</p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {cards.map((c, i) => {
            const Icon = c.icon;
            return (
              <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.1 }}
                className="rounded-2xl overflow-hidden shadow-xl border-2 border-[#E7E2D6]">
                <div className={`bg-gradient-to-r ${c.color} p-5 text-white`}>
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                      <Icon className="w-6 h-6" />
                    </div>
                    <h3 className="text-2xl font-bold" style={{ fontFamily: 'Spectral, serif' }}>{c.label}</h3>
                  </div>
                </div>
                <div className="p-5 bg-white">
                  <p className="text-[#1B2A4A] text-sm sm:text-base leading-relaxed">{c.text}</p>
                </div>
              </motion.div>
            );
          })}
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }}
          className="rounded-2xl bg-gradient-to-r from-[#1B2A4A] to-[#2A3D63] p-6 text-white text-center shadow-xl">
          <p className="text-xs uppercase tracking-widest text-[#C8A951] mb-2 font-bold">Declaración Central</p>
          <p className="text-xl sm:text-3xl font-bold italic" style={{ fontFamily: 'Spectral, serif' }}>
            Formamos discípulos, levantamos líderes,<br />multiplicamos el Reino.
          </p>
        </motion.div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
          <p className="text-center text-sm uppercase tracking-widest text-[#1B2A4A] font-bold mb-3">Nuestros Valores</p>
          <div className="flex flex-wrap gap-2 justify-center">
            {valores.map((v, i) => (
              <motion.div
                key={v}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.5 + i * 0.08, type: 'spring' }}
                className="px-4 py-2 rounded-full bg-gradient-to-r from-[#C8A951] to-[#E2CF8A] text-[#1B2A4A] font-semibold text-sm shadow-md"
              >
                {v}
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
};

// ============================================================
// SLIDE: LEMA + NEHEMÍAS
// ============================================================
export const SlideLemaNehemias = () => {
  const puertasNeh = [
    { num: 1, nombre: 'Puerta de las Ovejas', descripcion: 'Evangelismo', ref: '' },
    { num: 2, nombre: 'Puerta del Pescado', descripcion: 'Alcance', ref: '3:3' },
    { num: 3, nombre: 'Puerta Vieja', descripcion: 'Fundamento · Discipulado', ref: '3:6' },
    { num: 4, nombre: 'Puerta del Valle', descripcion: 'Sanidad (LBS)', ref: '3:13' },
    { num: 5, nombre: 'Puerta del Muladar', descripcion: 'Limpieza · Santidad', ref: '3:14' },
    { num: 6, nombre: 'Puerta de la Fuente', descripcion: 'Espíritu Santo · Ayuno · Oración', ref: '3:15' },
    { num: 7, nombre: 'Puerta de las Aguas', descripcion: 'La Palabra', ref: '3:26' },
    { num: 8, nombre: 'Puerta del Caballo', descripcion: 'Guerra espiritual', ref: '3:28' },
    { num: 9, nombre: 'Puerta Oriental', descripcion: 'Expectativa del mover de Dios', ref: '3:29' },
  ];
  return (
    <div className="min-h-full px-6 py-10 bg-gradient-to-br from-[#1B2A4A] via-[#2A3D63] to-[#0F1A33] text-white">
      <div className="max-w-5xl mx-auto">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-8">
          <div className="inline-flex items-center gap-1.5 bg-[#C8A951] text-[#1B2A4A] rounded-full px-3 py-1 mb-4 font-bold text-xs uppercase tracking-widest">
            <Flame className="w-3 h-3" /> Lema del Año
          </div>
          <h2 className="text-3xl sm:text-5xl font-bold mb-3" style={{ fontFamily: 'Spectral, serif' }}>
            Año de <span className="text-[#C8A951]">Cosecha</span><br className="sm:hidden" /> y <span className="text-[#C8A951]">Restitución</span>
          </h2>
          <p className="text-white/60 italic mt-3">Las 9 Puertas en Nehemías 3</p>
        </motion.div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
          {puertasNeh.map((p, i) => (
            <motion.div
              key={p.num}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.05 + i * 0.05 }}
              className="p-3 rounded-xl bg-white/5 backdrop-blur-sm border border-[#C8A951]/20 hover:border-[#C8A951]/60 transition-colors"
            >
              <div className="flex items-baseline gap-2 mb-1">
                <div className="w-7 h-7 rounded-full bg-[#C8A951] text-[#1B2A4A] font-bold text-xs flex items-center justify-center shrink-0">{p.num}</div>
                {p.ref && <span className="text-[10px] text-[#C8A951] font-mono">Neh {p.ref}</span>}
              </div>
              <p className="font-bold text-xs sm:text-sm leading-tight mb-0.5">{p.nombre}</p>
              <p className="text-[10px] sm:text-xs text-white/60 leading-snug">{p.descripcion}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ============================================================
// SLIDE: INTRODUCCIÓN DEL MANUAL (rediseño horizontal — fill 16:9)
// Nota: el PNG vertical oficial (IMAGEN_INTRODUCCION) se conserva
// SOLO en el manual imprimible. Aquí reconstruimos el contenido
// con un layout apaisado elegante y animado.
// ============================================================
export const SlideIntroManual = () => {
  const pilares = [
    { n: '01', t: 'El corazón del sistema', d: 'Visión, misión y valores que sostienen todo.' },
    { n: '02', t: 'Base bíblica sólida', d: 'Las 9 Puertas en Nehemías 3 · el principio del Tiempo 3.' },
    { n: '03', t: 'Proceso claro', d: 'De persona a discípulo, de discípulo a líder — en 7 semanas.' },
    { n: '04', t: 'Herramientas prácticas', d: 'Para mentores, líderes de puerta y supervisores.' },
    { n: '05', t: 'Estrategia de ganar', d: 'Metas concretas, indicadores medibles y plan de acción.' },
  ];

  return (
    <div className="min-h-full w-full px-4 sm:px-10 py-6 sm:py-8 bg-gradient-to-br from-[#0F1A33] via-[#1B2A4A] to-[#0F1A33] text-white relative overflow-hidden flex flex-col">
      {/* Decorativos de fondo */}
      <div className="absolute inset-0 opacity-[0.08] pointer-events-none" style={{
        backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(200,169,81,0.6) 1px, transparent 0)',
        backgroundSize: '28px 28px'
      }} />
      <div className="absolute -top-32 -right-32 w-[28rem] h-[28rem] bg-[#C8A951]/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-32 -left-32 w-[28rem] h-[28rem] bg-[#3FB8AF]/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header del slide */}
      <motion.div
        initial={{ opacity: 0, y: -14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="text-center mb-5 sm:mb-7 relative z-10"
      >
        <div className="inline-flex items-center gap-1.5 bg-[#C8A951] text-[#0F1A33] rounded-full px-3 py-1 mb-2 font-bold text-[10px] sm:text-xs uppercase tracking-[0.25em]">
          <BookOpen className="w-3 h-3" /> Introducción del Manual
        </div>
        <h2 className="text-2xl sm:text-4xl md:text-5xl font-bold leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
          Una <span className="italic text-[#C8A951]">Invitación</span>
          <span className="text-white/60"> a ver la iglesia con nuevos ojos</span>
        </h2>
        <div className="w-20 h-0.5 bg-gradient-to-r from-transparent via-[#C8A951] to-transparent mx-auto mt-3" />
      </motion.div>

      {/* Layout apaisado: 2 columnas */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 lg:gap-8 items-stretch flex-1 relative z-10">
        {/* Columna izquierda: cita hero + promesa */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="lg:col-span-5 flex flex-col justify-center space-y-4"
        >
          <div className="relative">
            <div className="absolute -top-6 -left-2 text-[#C8A951]/30 text-8xl leading-none font-serif select-none">“</div>
            <p className="relative text-base sm:text-lg md:text-xl leading-relaxed text-white/90 italic pl-4 border-l-2 border-[#C8A951]/60" style={{ fontFamily: 'Spectral, serif' }}>
              Hay vidas esperando ser <span className="text-[#C8A951] not-italic font-semibold">alcanzadas</span>,
              sueños esperando ser <span className="text-[#C8A951] not-italic font-semibold">activados</span>,
              y puertas esperando ser <span className="text-[#C8A951] not-italic font-semibold">abiertas</span>.
            </p>
          </div>

          <p className="text-sm sm:text-base text-white/70 leading-relaxed">
            Este manual no nació de una idea humana; nació de una
            <span className="text-white font-semibold"> convicción profética</span>: que Dios quiere hacer algo
            nuevo, y lo hará a través de personas ordinarias dispuestas a servir con excelencia.
          </p>

          <div className="mt-2 p-4 rounded-xl bg-gradient-to-br from-[#C8A951]/15 to-[#E2CF8A]/5 border border-[#C8A951]/30">
            <p className="text-[10px] uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-1.5 flex items-center gap-1.5">
              <Sparkles className="w-3 h-3" /> Nuestra Promesa
            </p>
            <p className="text-sm sm:text-base text-white/90 leading-snug" style={{ fontFamily: 'Spectral, serif' }}>
              Si aplicas con disciplina lo que aquí está escrito,{' '}
              <span className="text-[#C8A951] font-bold">verás fruto</span>.
            </p>
          </div>
        </motion.div>

        {/* Columna derecha: 5 pilares numerados */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.25 }}
          className="lg:col-span-7 flex flex-col justify-center"
        >
          <p className="text-[10px] sm:text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-3 flex items-center gap-1.5">
            <Target className="w-3 h-3" /> ¿Qué encontrarás aquí?
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3">
            {pilares.map((p, i) => (
              <motion.div
                key={p.n}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.35 + i * 0.08 }}
                className="group relative flex items-start gap-3 p-3 sm:p-3.5 rounded-xl bg-white/5 backdrop-blur-sm border border-white/10 hover:border-[#C8A951]/50 hover:bg-white/[0.07] transition-colors"
              >
                <div className="shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-lg bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] text-[#0F1A33] flex items-center justify-center font-bold text-xs sm:text-sm shadow-md">
                  {p.n}
                </div>
                <div className="min-w-0">
                  <p className="font-bold text-white text-sm sm:text-base leading-tight" style={{ fontFamily: 'Spectral, serif' }}>{p.t}</p>
                  <p className="text-[11px] sm:text-xs text-white/60 leading-snug mt-0.5">{p.d}</p>
                </div>
              </motion.div>
            ))}

            {/* Tarjeta CTA final ocupando el hueco */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.35 + pilares.length * 0.08 }}
              className="relative flex items-center gap-3 p-3 sm:p-3.5 rounded-xl bg-gradient-to-br from-[#C8A951]/20 to-[#C8A951]/5 border border-[#C8A951]/40"
            >
              <div className="shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-lg bg-[#0F1A33] text-[#C8A951] flex items-center justify-center shadow-md">
                <Flame className="w-4 h-4 sm:w-5 sm:h-5" />
              </div>
              <div className="min-w-0">
                <p className="font-bold text-[#C8A951] text-sm sm:text-base leading-tight" style={{ fontFamily: 'Spectral, serif' }}>Hoy comienza algo nuevo</p>
                <p className="text-[11px] sm:text-xs text-white/70 leading-snug mt-0.5">Gira la página. El proceso ya empezó.</p>
              </div>
            </motion.div>
          </div>

          <p className="text-[10px] sm:text-xs text-white/40 italic mt-3 text-right">
            Léelo con lápiz en mano · con oración · con tu equipo al lado.
          </p>
        </motion.div>
      </div>
    </div>
  );
};

// ============================================================
// SLIDE: LEY 7 SEMANAS (con imagen 13 oficial)
// ============================================================
export const SlideLey7Semanas = () => (
  <div className="min-h-full px-4 sm:px-6 py-6 bg-gradient-to-br from-[#1B2A4A] via-[#2A3D63] to-[#1B2A4A] text-white">
    <div className="max-w-6xl mx-auto space-y-4">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
        <div className="inline-flex items-center gap-1.5 bg-[#C8A951] text-[#1B2A4A] rounded-full px-3 py-1 mb-2 font-bold text-xs uppercase tracking-widest">
          <Compass className="w-3 h-3" /> Recorrido Completo
        </div>
        <h2 className="text-2xl sm:text-4xl font-bold" style={{ fontFamily: 'Spectral, serif' }}>
          La Ley de las <span className="text-[#C8A951]">7 Semanas</span>
        </h2>
        <p className="text-xs sm:text-sm text-white/60 italic mt-1">
          Un proceso circular: de la invasión al retiro, y nuevamente al comienzo
        </p>
      </motion.div>

      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }}
        className="flex justify-center">
        <img
          src={IMAGEN_LEY_7_SEMANAS}
          alt="La Ley de las 7 Semanas - Recorrido completo"
          className="max-w-full max-h-[75vh] h-auto object-contain rounded-2xl shadow-2xl border-2 border-[#C8A951]/30 bg-white/5 backdrop-blur-sm p-2"
        />
      </motion.div>

      <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
        className="text-center text-xs sm:text-sm text-white/70 italic max-w-3xl mx-auto">
        "Persona → Discípulo → Obrero → Líder/Ministro"
      </motion.p>
    </div>
  </div>
);

// ============================================================
// SLIDE: MODELO CAP
// ============================================================
export const SlideModeloCAP = () => (
  <div className="min-h-full px-6 py-10 bg-gradient-to-br from-purple-900 via-[#1B2A4A] to-[#0F1A33] text-white">
    <div className="max-w-5xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
        <div className="inline-flex items-center gap-1.5 bg-[#C8A951] text-[#1B2A4A] rounded-full px-3 py-1 mb-4 font-bold text-xs uppercase tracking-widest">
          <Target className="w-3 h-3" /> Modelo CAP
        </div>
        <h2 className="text-3xl sm:text-5xl font-bold mb-2" style={{ fontFamily: 'Spectral, serif' }}>
          <span className="text-[#C8A951]">C</span>onsolidación y <span className="text-[#C8A951]">A</span>ctivación por <span className="text-[#C8A951]">P</span>uertas
        </h2>
        <p className="italic text-white/70 text-sm mt-2">"Escribe la visión y declárala..." — Habacuc 2:2</p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { icon: Target, titulo: 'El Don = La Llave', desc: 'Tu don es la llave que abre tu puerta en el Reino. Cuando conectamos a una persona correctamente, algo se abre.' },
          { icon: Users, titulo: 'El Cuerpo', desc: 'La iglesia funciona como un cuerpo: no todos hacen lo mismo, pero todos son necesarios. Cada miembro tiene una función específica.' },
          { icon: Rocket, titulo: '3 Niveles', desc: 'El crecimiento se da en: Formación · Seguimiento · Crecimiento.' },
        ].map((p, i) => {
          const Icon = p.icon;
          return (
            <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.1 }}
              className="p-5 rounded-2xl bg-white/5 backdrop-blur-sm border border-[#C8A951]/20 hover:border-[#C8A951]/60 transition-colors">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] flex items-center justify-center mb-3 shadow-lg">
                <Icon className="w-6 h-6 text-[#1B2A4A]" />
              </div>
              <h3 className="font-bold text-lg mb-2" style={{ fontFamily: 'Spectral, serif' }}>{p.titulo}</h3>
              <p className="text-sm text-white/70 leading-relaxed">{p.desc}</p>
            </motion.div>
          );
        })}
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
        className="rounded-xl bg-[#C8A951]/10 border border-[#C8A951]/40 p-5 text-center">
        <p className="text-[#C8A951] font-bold text-sm uppercase tracking-widest mb-1">Flujo del Sistema</p>
        <p className="text-sm sm:text-base text-white/90">
          Llega → Se recibe → Se conecta → Se identifica su don → Se asigna a una puerta → Se activa → Se discipula → Sirve y crece
        </p>
      </motion.div>
    </div>
  </div>
);

// ============================================================
// SLIDE: OPERACIÓN 72
// ============================================================
export const SlideOperacion72 = () => (
  <div className="min-h-full px-6 py-10 bg-gradient-to-br from-[#0F1A33] via-[#1B2A4A] to-purple-900 text-white relative overflow-hidden">
    <div className="absolute top-1/4 right-10 text-[280px] font-bold text-[#C8A951]/5 leading-none" style={{ fontFamily: 'Spectral, serif' }}>72</div>
    <div className="relative z-10 max-w-5xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
        <div className="inline-flex items-center gap-1.5 bg-purple-600/80 text-white rounded-full px-3 py-1 mb-4 font-bold text-xs uppercase tracking-widest">
          <Zap className="w-3 h-3" /> Operación
        </div>
        <h2 className="text-5xl sm:text-7xl font-bold mb-2" style={{ fontFamily: 'Spectral, serif' }}>
          <span className="text-[#C8A951]">72</span>
        </h2>
        <p className="text-lg sm:text-xl italic">Equipo por Puertas</p>
        <p className="text-white/60 text-sm mt-2">Base bíblica: Isaías 61:1-5</p>
      </motion.div>

      <div className="rounded-2xl bg-white/5 backdrop-blur-sm border border-[#C8A951]/30 p-5 sm:p-6">
        <p className="text-xs uppercase tracking-widest text-[#C8A951] font-bold mb-3">Principio del Tiempo 3</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
          {[
            { n: '3 días', l: 'Atender nuevos creyentes' },
            { n: '21 días', l: 'LBS (Liberación, Bendición, Sanidad)' },
            { n: '72 hrs', l: 'Operación inicial' },
            { n: '3 meses', l: 'Seguimiento continuo' },
          ].map((item, i) => (
            <motion.div key={i} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1 + i * 0.1 }}
              className="p-3 rounded-xl bg-[#C8A951]/10 border border-[#C8A951]/20">
              <p className="text-2xl font-bold text-[#C8A951]" style={{ fontFamily: 'Spectral, serif' }}>{item.n}</p>
              <p className="text-xs text-white/70 mt-1">{item.l}</p>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[
          { mes: 'Mes 1', tema: 'Profundizar en el LLAMADO', icon: Compass },
          { mes: 'Mes 2', tema: 'Profundizar en el PRIVILEGIO de servir', icon: Crown },
          { mes: 'Mes 3', tema: 'Devocional "Predestinado para ganar"', icon: Rocket },
        ].map((m, i) => {
          const Icon = m.icon;
          return (
            <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 + i * 0.1 }}
              className="p-4 rounded-xl bg-gradient-to-br from-purple-600/30 to-pink-600/20 border border-white/10">
              <Icon className="w-6 h-6 text-[#C8A951] mb-2" />
              <p className="text-xs text-[#C8A951] font-bold uppercase tracking-wider">{m.mes}</p>
              <p className="text-sm font-medium mt-1">{m.tema}</p>
            </motion.div>
          );
        })}
      </div>
    </div>
  </div>
);

// ============================================================
// SLIDE: LAS 9 PUERTAS (mockup de puertas reales, fila horizontal)
// Optimizado para pantalla LED 17ft x 7ft (ratio ~2.43:1):
// los 9 ministerios entran en UNA sola pantalla sin scroll, cada
// uno renderizado como una puerta de madera con marco, paneles
// y manija dorada (estilo "pasillo de puertas").
// ============================================================
const Door = ({ puerta, index }) => {
  const Icon = ICON_MAP[puerta.icon] || DoorOpen;
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 + index * 0.06, type: 'spring', stiffness: 80 }}
      className="relative h-full flex flex-col items-stretch min-w-0"
    >
      {/* Dintel: marco superior de la puerta */}
      <div className="bg-gradient-to-b from-[#3a2a1c] to-[#2a1d12] rounded-t-md shadow-md py-1 px-1.5 text-center shrink-0 border-x-2 border-t-2 border-[#1a110a]">
        <p className="text-[9px] xl:text-[10px] font-black text-[#C8A951] uppercase tracking-[0.18em] leading-tight whitespace-nowrap">
          Puerta {puerta.num}
        </p>
      </div>

      {/* Cuerpo de la puerta */}
      <div
        className={`relative flex-1 bg-gradient-to-b ${puerta.color} border-x-2 border-b-2 border-[#1a110a] shadow-2xl flex flex-col p-1.5 xl:p-2 overflow-hidden min-h-0`}
      >
        {/* Bisagras a la izquierda */}
        <span className="absolute left-0.5 top-3 w-1 h-3 bg-[#C8A951]/80 rounded-sm shadow-sm" aria-hidden="true" />
        <span className="absolute left-0.5 bottom-3 w-1 h-3 bg-[#C8A951]/80 rounded-sm shadow-sm" aria-hidden="true" />

        {/* Manija dorada */}
        <span
          className="absolute right-1 top-1/2 -translate-y-1/2 w-2 h-2 xl:w-2.5 xl:h-2.5 rounded-full bg-gradient-to-br from-[#F2D98F] to-[#A37C2C] ring-1 ring-black/20 shadow"
          aria-hidden="true"
        />

        {/* Highlight diagonal (efecto luz) */}
        <span
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'linear-gradient(135deg, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.05) 35%, transparent 60%)',
          }}
          aria-hidden="true"
        />

        {/* Panel superior (icono) */}
        <div className="relative z-[1] flex-[1.2] border-2 border-white/30 rounded-sm flex items-center justify-center bg-black/5 mb-1 min-h-0">
          <Icon className="w-6 h-6 sm:w-8 sm:h-8 xl:w-10 xl:h-10 text-white drop-shadow-lg" />
        </div>

        {/* Panel inferior (nombre) */}
        <div className="relative z-[1] flex-1 border-2 border-white/30 rounded-sm flex items-center justify-center text-center px-1 bg-black/5 min-h-0">
          <p
            className="text-white font-bold leading-[1.1] drop-shadow-md"
            style={{ fontSize: 'clamp(9px, 0.9vw, 14px)' }}
          >
            {puerta.nombre}
          </p>
        </div>
      </div>

      {/* Sombra del piso */}
      <div className="h-1 mx-1 bg-black/30 rounded-full blur-sm shrink-0" aria-hidden="true" />
    </motion.div>
  );
};

export const SlideLas9Puertas = () => (
  <div
    className="h-full w-full flex flex-col px-4 sm:px-6 py-4 xl:py-6 bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] overflow-hidden"
    data-testid="slide-9-puertas"
  >
    {/* Header compacto */}
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center mb-3 xl:mb-4 shrink-0"
    >
      <div className="inline-flex items-center gap-1.5 bg-[#1B2A4A] text-white rounded-full px-3 py-1 mb-2 font-bold text-[10px] xl:text-xs uppercase tracking-widest">
        <DoorOpen className="w-3 h-3" /> 9 Ministerios
      </div>
      <h2
        className="text-2xl sm:text-3xl xl:text-5xl font-bold text-[#1B2A4A] leading-tight"
        style={{ fontFamily: 'Spectral, serif' }}
      >
        Las <span className="text-[#C8A951]">9 Puertas</span> del Sistema
      </h2>
      <p className="text-[11px] xl:text-sm text-muted-foreground mt-1">
        Cada puerta organiza un ministerio con líderes, equipos y metas.
      </p>
    </motion.div>

    {/* Piso (linea de horizonte sutil) */}
    <div className="flex-1 grid grid-cols-9 gap-1.5 xl:gap-2 min-h-0 relative">
      {LAS_9_PUERTAS.map((p, i) => (
        <Door key={p.num} puerta={p} index={i} />
      ))}
    </div>

    {/* Linea del piso */}
    <div className="h-[2px] bg-gradient-to-r from-transparent via-[#1a110a]/30 to-transparent shrink-0 mt-1" aria-hidden="true" />
  </div>
);

// ============================================================
// SLIDE: ESTRUCTURA GENERAL
// ============================================================
export const SlideEstructura = () => {
  const jerarquia = [
    { rol: 'Pastor Principal', icon: Crown, color: 'from-[#C8A951] to-[#E2CF8A]' },
    { rol: 'Coordinador General', icon: Shield, color: 'from-purple-600 to-indigo-700' },
    { rol: 'Líderes de Puertas (×9)', icon: DoorOpen, color: 'from-[#1FA6A0] to-teal-600' },
    { rol: 'Equipos de Servidores', icon: Users, color: 'from-blue-500 to-cyan-600' },
    { rol: 'Iglesia · Miembros · Células', icon: Heart, color: 'from-rose-500 to-pink-600' },
  ];
  return (
    <div className="min-h-full px-6 py-10 bg-gradient-to-br from-[#1B2A4A] via-[#2A3D63] to-[#1B2A4A] text-white">
      <div className="max-w-4xl mx-auto">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-6">
          <h2 className="text-3xl sm:text-5xl font-bold" style={{ fontFamily: 'Spectral, serif' }}>
            Estructura <span className="text-[#C8A951]">General</span>
          </h2>
          <p className="text-white/60 text-sm mt-2">Jerarquía del Sistema Celular</p>
        </motion.div>

        <div className="space-y-2">
          {jerarquia.map((n, i) => {
            const Icon = n.icon;
            return (
              <motion.div key={i} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 + i * 0.1 }}
                className={`flex items-center gap-3 p-4 rounded-xl bg-gradient-to-r ${n.color} shadow-lg`}
                style={{ marginLeft: `${i * 5}%` }}>
                <div className="w-11 h-11 rounded-full bg-white/25 backdrop-blur-sm flex items-center justify-center shrink-0">
                  <Icon className="w-6 h-6 text-white" />
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider opacity-80">Nivel {i + 1}</p>
                  <p className="font-bold text-base sm:text-lg">{n.rol}</p>
                </div>
              </motion.div>
            );
          })}
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }}
          className="mt-6 p-5 rounded-xl bg-[#C8A951]/10 border border-[#C8A951]/30 text-center">
          <p className="italic text-sm sm:text-base">
            "Las células <span className="font-bold text-[#C8A951]">detectan</span>,
            las puertas <span className="font-bold text-[#C8A951]">responden</span>,
            el liderazgo <span className="font-bold text-[#C8A951]">supervisa</span>,
            Dios <span className="font-bold text-[#C8A951]">transforma</span> vidas."
          </p>
        </motion.div>
      </div>
    </div>
  );
};

// ============================================================
// SLIDE: LÍDER DE PUERTA
// ============================================================
export const SlideLider = () => {
  const funciones = [
    { titulo: 'Cuidar', desc: 'Conocer a su gente, estar presente y disponible', icon: Heart, color: 'from-rose-500 to-pink-600' },
    { titulo: 'Ubicar', desc: 'Identificar dones y conectar con oportunidades', icon: Compass, color: 'from-blue-500 to-indigo-600' },
    { titulo: 'Activar', desc: 'Dar oportunidades, impulsar al siguiente paso', icon: Rocket, color: 'from-emerald-500 to-teal-600' },
    { titulo: 'Desarrollar', desc: 'Formar nuevos líderes, multiplicar el liderazgo', icon: Crown, color: 'from-[#C8A951] to-[#E2CF8A]' },
  ];
  return (
    <div className="min-h-full px-6 py-10 bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
      <div className="max-w-5xl mx-auto space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
          <h2 className="text-3xl sm:text-5xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
            El <span className="text-[#C8A951]">Líder</span> de Puerta
          </h2>
          <p className="text-muted-foreground text-sm mt-2">No es un jefe. Es formador · cuidador · activador.</p>
        </motion.div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {funciones.map((f, i) => {
            const Icon = f.icon;
            return (
              <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.1 }}
                className="rounded-2xl overflow-hidden shadow-xl">
                <div className={`bg-gradient-to-br ${f.color} p-4 text-white aspect-video flex flex-col items-center justify-center text-center`}>
                  <Icon className="w-10 h-10 mb-2" />
                  <h3 className="text-xl font-bold" style={{ fontFamily: 'Spectral, serif' }}>{f.titulo}</h3>
                </div>
                <div className="p-3 bg-white border-2 border-t-0 border-[#E7E2D6]">
                  <p className="text-xs sm:text-sm text-[#1B2A4A] leading-snug">{f.desc}</p>
                </div>
              </motion.div>
            );
          })}
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}
          className="rounded-xl bg-gradient-to-r from-[#1B2A4A] to-[#2A3D63] p-5 text-white text-center shadow-xl">
          <p className="italic text-base sm:text-lg">
            "No solo queremos consolidar personas,<br/>
            <span className="text-[#C8A951] font-bold">queremos consolidarlas en una puerta.</span>"
          </p>
        </motion.div>
      </div>
    </div>
  );
};

// ============================================================
// SLIDE: MENTOR
// ============================================================
export const SlideMentor = () => (
  <div className="min-h-full px-6 py-10 bg-gradient-to-br from-[#1B2A4A] via-[#2A3D63] to-[#1B2A4A] text-white">
    <div className="max-w-5xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
        <div className="inline-flex items-center gap-1.5 bg-[#C8A951] text-[#1B2A4A] rounded-full px-3 py-1 mb-3 font-bold text-xs uppercase tracking-widest">
          <GraduationCap className="w-3 h-3" /> Mentor
        </div>
        <h2 className="text-3xl sm:text-5xl font-bold" style={{ fontFamily: 'Spectral, serif' }}>
          Propósito del <span className="text-[#C8A951]">Mentor</span>
        </h2>
        <p className="text-white/60 italic text-sm mt-2">"Lo que has oído de mí ... esto encarga a hombres fieles..." — 2 Timoteo 2:2</p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}
          className="p-5 rounded-2xl bg-white/5 backdrop-blur-sm border border-[#C8A951]/20">
          <h3 className="font-bold text-lg mb-3 text-[#C8A951]" style={{ fontFamily: 'Spectral, serif' }}>El mentor existe para:</h3>
          <ul className="space-y-2">
            {['Afirmar la fe del nuevo creyente', 'Ayudarlo a cambiar su estilo de vida', 'Integrarlo a la iglesia', 'Prepararlo para servir'].map((p, i) => (
              <li key={i} className="flex items-start gap-2 text-sm"><CheckCircle2 className="w-4 h-4 text-[#C8A951] shrink-0 mt-0.5" /><span>{p}</span></li>
            ))}
          </ul>
        </motion.div>

        <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}
          className="p-5 rounded-2xl bg-white/5 backdrop-blur-sm border border-[#C8A951]/20">
          <h3 className="font-bold text-lg mb-3 text-[#C8A951]" style={{ fontFamily: 'Spectral, serif' }}>Responsabilidades</h3>
          <ul className="space-y-2">
            {['Contacto semanal (llamada/mensaje)', 'Reunión de discipulado (1×/sem)', 'Cuidado espiritual (orar, escuchar)', 'Integración (célula + puerta)'].map((p, i) => (
              <li key={i} className="flex items-start gap-2 text-sm"><Star className="w-4 h-4 text-[#C8A951] shrink-0 mt-0.5" /><span>{p}</span></li>
            ))}
          </ul>
        </motion.div>
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
        className="rounded-2xl bg-gradient-to-r from-[#C8A951]/20 to-[#E2CF8A]/10 border border-[#C8A951]/40 p-4 sm:p-5">
        <p className="text-xs text-[#C8A951] font-bold uppercase tracking-widest mb-3">Discipulado 8 Semanas</p>
        <div className="grid grid-cols-4 md:grid-cols-8 gap-1.5">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((n, i) => (
            <div key={n} className="p-2 rounded-lg bg-white/5 border border-white/10 text-center">
              <p className="text-[10px] opacity-70">S{n}</p>
              <p className="text-xs font-bold mt-0.5 leading-tight">
                {i === 0 && 'Salvación'}
                {i === 1 && 'Oración'}
                {i === 2 && 'Biblia'}
                {i === 3 && 'Iglesia'}
                {i === 4 && 'Santidad'}
                {i === 5 && 'Visión'}
                {i === 6 && 'Don'}
                {i === 7 && 'Liderazgo'}
              </p>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  </div>
);

// ============================================================
// SLIDE: ESTRATEGIA GANAR
// ============================================================
export const SlideEstrategia = () => (
  <div className="min-h-full px-6 py-10 bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
    <div className="max-w-5xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
        <h2 className="text-3xl sm:text-5xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
          Estrategia de <span className="text-[#C8A951]">Ganar</span>
        </h2>
        <p className="text-muted-foreground text-sm mt-2">Metas · Plan · Ejecución</p>
      </motion.div>

      <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }}
        className="rounded-2xl bg-gradient-to-r from-[#1B2A4A] to-[#2A3D63] p-6 sm:p-8 text-white text-center shadow-xl">
        <p className="text-xs uppercase tracking-widest text-[#C8A951] font-bold mb-2">Meta Principal</p>
        <p className="text-6xl sm:text-8xl font-bold text-[#C8A951]" style={{ fontFamily: 'Spectral, serif' }}>40</p>
        <p className="text-lg sm:text-xl italic mt-2">Líderes Servidores</p>
        <p className="text-xs text-white/60 mt-1">Primera etapa de consolidación</p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[
          { num: '2 sem', desc: 'MCD y NPT, Bienvenida (2×/mes)', icon: Calendar },
          { num: '3 disc.', desc: 'Tres niveles de discipulado', icon: BookOpen },
          { num: '5 inv.', desc: 'Invasiones en el año', icon: Rocket },
        ].map((m, i) => {
          const Icon = m.icon;
          return (
            <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + i * 0.1 }}
              className="p-5 rounded-xl bg-white shadow-md border-2 border-[#E7E2D6] text-center">
              <Icon className="w-8 h-8 mx-auto mb-2 text-[#C8A951]" />
              <p className="text-2xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>{m.num}</p>
              <p className="text-sm text-muted-foreground mt-1">{m.desc}</p>
            </motion.div>
          );
        })}
      </div>
    </div>
  </div>
);

// ============================================================
// SLIDE: CONSOLIDADO DE PUERTA
// ============================================================
export const SlideConsolidado = () => {
  const indicadores = [
    { titulo: 'Ubicación', desc: 'Tiene una puerta definida', icon: Compass, color: 'from-blue-600 to-cyan-700' },
    { titulo: 'Activación', desc: 'Ya está sirviendo', icon: Rocket, color: 'from-emerald-600 to-teal-700' },
    { titulo: 'Cobertura', desc: 'Tiene un líder que lo conoce', icon: Shield, color: 'from-purple-600 to-indigo-700' },
    { titulo: 'Proceso', desc: 'Está en formación continua', icon: GraduationCap, color: 'from-[#C8A951] to-[#E2CF8A]' },
  ];
  return (
    <div className="min-h-full px-6 py-10 bg-gradient-to-br from-[#1B2A4A] via-[#2A3D63] to-[#0F1A33] text-white">
      <div className="max-w-5xl mx-auto space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
          <h2 className="text-3xl sm:text-5xl font-bold" style={{ fontFamily: 'Spectral, serif' }}>
            Consolidado de <span className="text-[#C8A951]">Puerta</span>
          </h2>
          <p className="italic text-white/70 text-sm mt-2">No por emoción. Por EVIDENCIA.</p>
        </motion.div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {indicadores.map((ind, i) => {
            const Icon = ind.icon;
            return (
              <motion.div key={i} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.15 + i * 0.1 }}
                className="rounded-2xl overflow-hidden shadow-xl">
                <div className={`bg-gradient-to-br ${ind.color} p-4 aspect-square flex flex-col items-center justify-center text-white text-center`}>
                  <div className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center mb-2">
                    <Icon className="w-7 h-7" />
                  </div>
                  <p className="text-[9px] uppercase tracking-widest opacity-80 font-bold">Indicador {i + 1}</p>
                  <h3 className="text-xl font-bold mt-1" style={{ fontFamily: 'Spectral, serif' }}>{ind.titulo}</h3>
                  <p className="text-[11px] opacity-90 mt-1">{ind.desc}</p>
                </div>
              </motion.div>
            );
          })}
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}
          className="rounded-xl bg-[#C8A951]/10 border border-[#C8A951]/40 p-5 text-center">
          <p className="text-xl sm:text-2xl italic" style={{ fontFamily: 'Spectral, serif' }}>
            "No queremos solo personas presentes,<br />
            <span className="text-[#C8A951] font-bold">queremos personas firmes.</span>"
          </p>
        </motion.div>
      </div>
    </div>
  );
};

// ============================================================
// SLIDE: REUNIÓN SUPERVISORES
// ============================================================
export const SlideReunionSupervisores = () => {
  const agenda = [
    { tiempo: '5 min', bloque: 'Inicio', detalle: 'Oración · Ministración · Bienvenida' },
    { tiempo: '5 min c/u', bloque: 'Evaluación', detalle: '¿Cuántos líderes? ¿Quién avanza? ¿Quién necesita ayuda?' },
    { tiempo: '10 min', bloque: 'Detección', detalle: '¿Dónde se detiene la gente? ¿Qué puerta falla?' },
    { tiempo: '5 min', bloque: 'Ajustes', detalle: '¿Qué corregir? ¿Qué reforzar?' },
    { tiempo: '5 min', bloque: 'Activación', detalle: 'Orar · Declarar claridad, multiplicación, movimiento' },
  ];
  return (
    <div className="min-h-full px-6 py-10 bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
      <div className="max-w-5xl mx-auto space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
          <h2 className="text-3xl sm:text-5xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
            Reunión Mensual
          </h2>
          <p className="text-muted-foreground text-sm mt-2">Supervisores · Agenda y reglas</p>
        </motion.div>

        <div className="space-y-2">
          {agenda.map((a, i) => (
            <motion.div key={i} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 + i * 0.08 }}
              className="flex items-center gap-3 p-3 sm:p-4 bg-white rounded-xl shadow-md border-l-4 border-[#C8A951]">
              <div className="w-16 h-12 rounded-lg bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] text-[#1B2A4A] font-bold flex items-center justify-center text-xs shrink-0">{a.tiempo}</div>
              <div className="flex-1">
                <p className="font-bold text-[#1B2A4A] text-sm sm:text-base">{a.bloque}</p>
                <p className="text-xs sm:text-sm text-muted-foreground">{a.detalle}</p>
              </div>
            </motion.div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
            className="p-4 rounded-xl bg-red-50 border-2 border-red-200">
            <p className="text-red-600 font-bold text-xs uppercase tracking-widest mb-2">❌ Nunca</p>
            <p className="text-xs sm:text-sm text-[#1B2A4A]">Alargar · Desviarse · Contar historias largas</p>
          </motion.div>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.65 }}
            className="p-4 rounded-xl bg-emerald-50 border-2 border-emerald-200">
            <p className="text-emerald-600 font-bold text-xs uppercase tracking-widest mb-2">✅ Sí hacer</p>
            <p className="text-xs sm:text-sm text-[#1B2A4A]">Ir al punto · Escuchar · Decidir</p>
          </motion.div>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// SLIDE: CIERRE
// ============================================================
export const SlideCierre = () => {
  const llamados = [
    { texto: 'Hay una puerta para servir', icon: DoorOpen },
    { texto: 'Hay una función para cada don', icon: Target },
    { texto: 'Hay una necesidad en cada área', icon: HandHeart },
    { texto: 'Hay una generación que necesita ser cuidada', icon: Users },
  ];
  return (
    <div className="min-h-full px-6 py-10 bg-gradient-to-br from-[#0F1A33] via-[#1B2A4A] to-purple-900 text-white relative overflow-hidden">
      <div className="absolute inset-0 opacity-10" style={{
        backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.3) 1px, transparent 0)',
        backgroundSize: '32px 32px'
      }} />
      <div className="absolute top-0 right-0 w-80 h-80 bg-[#C8A951]/10 rounded-full blur-3xl" />
      <div className="absolute bottom-0 left-0 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl" />

      <div className="relative z-10 max-w-4xl mx-auto">
        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring' }} className="flex justify-center mb-6">
          <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-full bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] flex items-center justify-center shadow-2xl">
            <Flame className="w-10 h-10 sm:w-12 sm:h-12 text-[#1B2A4A]" />
          </div>
        </motion.div>

        <motion.h2 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="text-center text-3xl sm:text-5xl font-bold mb-2" style={{ fontFamily: 'Spectral, serif' }}>
          Llamado a <span className="text-[#C8A951]">Servir</span>
        </motion.h2>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
          className="text-center text-sm sm:text-base text-[#C8A951] font-bold uppercase tracking-widest mb-8">
          Año de Cosecha y Restitución
        </motion.p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
          {llamados.map((l, i) => {
            const Icon = l.icon;
            return (
              <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 + i * 0.1 }}
                className="flex items-center gap-3 p-4 rounded-xl bg-white/5 backdrop-blur-sm border border-[#C8A951]/20">
                <div className="w-10 h-10 rounded-full bg-[#C8A951]/20 flex items-center justify-center shrink-0">
                  <Icon className="w-5 h-5 text-[#C8A951]" />
                </div>
                <p className="text-sm sm:text-base font-medium">{l.texto}</p>
              </motion.div>
            );
          })}
        </div>

        <motion.blockquote initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1 }}
          className="border-l-4 border-[#C8A951] pl-4 italic text-white/80 text-sm sm:text-base">
          "Porque de la manera que en un cuerpo tenemos muchos miembros, pero no todos los miembros tienen la misma función..."
          <cite className="block mt-2 not-italic text-[#C8A951] font-bold">— Romanos 12:4</cite>
        </motion.blockquote>
      </div>
    </div>
  );
};

// ============================================================
// Renderer central
// ============================================================
export const SlideRenderer = ({ slide }) => {
  if (!slide) return null;
  switch (slide.type) {
    case 'portada': return <SlidePortada slide={slide} />;
    case 'intro-manual': return <SlideIntroManual />;
    case 'identidad': return <SlideIdentidad />;
    case 'lema-nehemias': return <SlideLemaNehemias />;
    case 'ley-7-semanas': return <SlideLey7Semanas />;
    case 'modelo-cap': return <SlideModeloCAP />;
    case 'operacion-72': return <SlideOperacion72 />;
    case 'las-9-puertas': return <SlideLas9Puertas />;
    case 'estructura': return <SlideEstructura />;
    case 'lider': return <SlideLider />;
    case 'mentor': return <SlideMentor />;
    case 'estrategia': return <SlideEstrategia />;
    case 'consolidado': return <SlideConsolidado />;
    case 'reunion': return <SlideReunionSupervisores />;
    case 'cierre': return <SlideCierre />;
    default: return <div className="p-10 text-center">Slide: {slide.id}</div>;
  }
};
