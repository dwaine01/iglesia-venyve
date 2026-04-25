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
// SLIDE: LAS 9 PUERTAS (estilo logo: puerta entreabierta 3D
// con estela dorada de luz, en grid 3x3 + nombre al lado).
// Inspirado en logos clasicos de "Puertas Abiertas".
// ============================================================
const OpenDoor3D = ({ puerta }) => {
  const Icon = ICON_MAP[puerta.icon] || DoorOpen;
  return (
    <div
      className="relative shrink-0"
      style={{
        width: 'clamp(64px, 6.5vw, 110px)',
        height: 'clamp(86px, 8.6vw, 145px)',
        perspective: '550px',
      }}
    >
      {/* Estela dorada de luz debajo y alrededor */}
      <div
        className="absolute pointer-events-none"
        style={{
          left: '-30%',
          right: '-30%',
          bottom: '-20%',
          height: '55%',
          background:
            'radial-gradient(ellipse at center, rgba(242,217,143,0.7) 0%, rgba(242,217,143,0.35) 35%, rgba(200,169,81,0.12) 60%, transparent 80%)',
          filter: 'blur(2px)',
        }}
        aria-hidden="true"
      />

      {/* Marco / sombra interior (interior oscuro de la habitacion detras) */}
      <div
        className="absolute right-0 top-0 bottom-0 rounded-sm"
        style={{
          width: '78%',
          background: 'linear-gradient(135deg, #0a0a0f 0%, #1a1a25 60%, #2a2a38 100%)',
          boxShadow: 'inset 4px 0 8px rgba(0,0,0,0.6)',
        }}
        aria-hidden="true"
      />

      {/* Hoja de la puerta abierta (rotada en perspectiva) */}
      <div
        className={`absolute right-0 top-0 bottom-0 rounded-sm bg-gradient-to-br ${puerta.color} shadow-[0_8px_18px_-6px_rgba(0,0,0,0.5)]`}
        style={{
          width: '78%',
          transform: 'rotateY(-32deg)',
          transformOrigin: 'right center',
        }}
      >
        {/* Highlight en la hoja */}
        <span
          className="absolute inset-0 rounded-sm pointer-events-none"
          style={{
            background:
              'linear-gradient(135deg, rgba(255,255,255,0.28) 0%, rgba(255,255,255,0.08) 40%, transparent 70%)',
          }}
          aria-hidden="true"
        />

        {/* Numero pequeno dentro de la puerta */}
        <span
          className="absolute top-1 left-1 text-white font-black leading-none drop-shadow-md"
          style={{
            fontFamily: 'Spectral, serif',
            fontSize: 'clamp(10px, 1vw, 16px)',
          }}
        >
          {puerta.num}
        </span>

        {/* Icono centrado */}
        <span className="absolute inset-0 flex items-center justify-center">
          <Icon className="w-6 h-6 sm:w-7 sm:h-7 xl:w-8 xl:h-8 text-white/95 drop-shadow-md" />
        </span>

        {/* Manija dorada (en el borde izquierdo de la hoja, donde se abre) */}
        <span
          className="absolute left-1 top-1/2 -translate-y-1/2 w-1 h-1.5 rounded-full bg-gradient-to-br from-[#F8E8B4] to-[#A37C2C] ring-1 ring-black/40 shadow"
          aria-hidden="true"
        />
      </div>

      {/* Brillito chispa dorada (acento decorativo a la derecha) */}
      <span
        className="absolute -right-1 bottom-2 w-1.5 h-1.5 rounded-full bg-[#F2D98F] shadow-[0_0_8px_rgba(242,217,143,0.9)]"
        aria-hidden="true"
      />
    </div>
  );
};

const DoorCard = ({ puerta, index }) => (
  <motion.div
    initial={{ opacity: 0, y: 18, scale: 0.95 }}
    animate={{ opacity: 1, y: 0, scale: 1 }}
    transition={{ delay: 0.05 + index * 0.06, type: 'spring', stiffness: 95 }}
    className="flex items-center gap-3 xl:gap-4 px-2 xl:px-3 py-2"
  >
    <OpenDoor3D puerta={puerta} />

    {/* Texto: PUERTA N + nombre del ministerio en color */}
    <div className="flex-1 min-w-0">
      <p
        className="font-semibold uppercase tracking-[0.18em] text-[#1B2A4A]/55 leading-none mb-1"
        style={{ fontSize: 'clamp(8px, 0.65vw, 11px)' }}
      >
        Puerta {puerta.num}
      </p>
      <p
        className="font-extrabold uppercase leading-[1.05]"
        style={{
          color: puerta.accent,
          fontFamily: 'Spectral, serif',
          fontSize: 'clamp(13px, 1.35vw, 22px)',
          letterSpacing: '0.01em',
        }}
      >
        {puerta.nombre}
      </p>
    </div>
  </motion.div>
);

export const SlideLas9Puertas = () => (
  <div
    className="h-full w-full flex flex-col px-4 sm:px-6 py-5 xl:py-7 bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] overflow-hidden"
    data-testid="slide-9-puertas"
  >
    {/* Encabezado */}
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center shrink-0 mb-2 xl:mb-3"
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

    {/* Grid 3x3 de puertas abiertas con sus nombres */}
    <div className="flex-1 flex items-center justify-center min-h-0 px-4 xl:px-8 py-2">
      <div className="grid grid-cols-3 grid-rows-3 gap-3 xl:gap-4 w-full h-full max-w-[1500px] mx-auto">
        {LAS_9_PUERTAS.map((p, i) => (
          <DoorCard key={p.num} puerta={p} index={i} />
        ))}
      </div>
    </div>
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
// SLIDE: ÍNDICE (página 2 del manual)
// ============================================================
export const SlideIndice = () => (
  <div
    className="h-full w-full flex flex-col px-8 sm:px-12 py-7 xl:py-10 bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] overflow-hidden"
    data-testid="slide-indice"
  >
    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="shrink-0 mb-5">
      <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-1">Contenido del Manual</p>
      <h1 className="text-4xl sm:text-5xl xl:text-7xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
        Índice
      </h1>
      <div className="flex items-center gap-3 mt-3">
        <div className="w-20 h-1 bg-[#C8A951]" />
        <p className="text-xs xl:text-sm italic text-[#1B2A4A]/60">29 páginas · 9 puertas · 7 semanas</p>
      </div>
    </motion.div>

    <div className="flex-1 grid grid-cols-2 gap-6 xl:gap-10 min-h-0 overflow-hidden">
      {/* Columna I: Fundamentos + Liderazgo */}
      <div className="flex flex-col gap-5 min-h-0">
        <IndiceParte numeral="I" titulo="Fundamentos" items={[
          ['', 'Una Invitación', '3'],
          ['', '¿Para quién? · Promesa', '4'],
          ['', 'Panorama · Infografía', '5'],
          ['01', 'Nuestra Identidad', '6'],
          ['02', '9 Puertas en Nehemías 3', '7'],
          ['03', 'La Ley de las 7 Semanas', '8'],
          ['04', 'Modelo CAP', '10'],
          ['05', 'Operación 72', '11'],
          ['06', 'Las 9 Puertas (Intro)', '12'],
        ]} />
        <IndiceParte numeral="III" titulo="Liderazgo y Formación" items={[
          ['16', 'Estructura General', '22'],
          ['17', 'El Líder de Puerta', '23'],
          ['18', 'Propósito del Mentor', '24'],
          ['19', 'Discipulado en 8 Semanas', '25'],
        ]} />
      </div>

      {/* Columna II: 9 Puertas + Estrategia */}
      <div className="flex flex-col gap-5 min-h-0">
        <IndiceParte numeral="II" titulo="Las 9 Puertas del Sistema" items={LAS_9_PUERTAS.map((p, i) => [
          `P${p.num}`, p.nombre, String(13 + i),
        ])} />
        <IndiceParte numeral="IV" titulo="Estrategia y Ejecución" items={[
          ['20', 'Consolidado de Puerta', '26'],
          ['21', 'Reunión de Supervisores', '27'],
          ['22', 'Estrategia de Ganar', '28'],
          ['', 'Llamado Final', '29'],
        ]} />
      </div>
    </div>
  </div>
);

const IndiceParte = ({ numeral, titulo, items }) => (
  <div className="flex flex-col min-h-0">
    <div className="flex items-baseline gap-2 mb-2 pb-2 border-b-2 border-[#C8A951]/40 shrink-0">
      <span className="text-2xl xl:text-3xl font-bold text-[#C8A951]" style={{ fontFamily: 'Spectral, serif' }}>{numeral}</span>
      <p className="text-[10px] xl:text-xs uppercase tracking-widest text-[#C8A951] font-bold">{titulo}</p>
    </div>
    <div className="flex-1 overflow-y-auto pr-1">
      {items.map(([num, t, pag], i) => (
        <div key={i} className="flex items-baseline gap-2 py-0.5 text-[#1B2A4A] border-b border-dotted border-[#1B2A4A]/15">
          {num && <span className="text-[10px] xl:text-xs font-bold text-[#C8A951] w-7 shrink-0">{num}</span>}
          {!num && <span className="w-7 shrink-0" />}
          <span className="flex-1 text-xs xl:text-sm leading-tight" style={{ fontFamily: 'Spectral, serif' }}>{t}</span>
          <span className="text-[10px] xl:text-xs font-mono text-[#1B2A4A]/50 shrink-0">{pag}</span>
        </div>
      ))}
    </div>
  </div>
);

// ============================================================
// SLIDE: UNA INVITACIÓN (página 3 del manual)
// ============================================================
export const SlideInvitacion = () => (
  <div className="h-full w-full flex flex-col px-8 xl:px-16 py-8 xl:py-12 bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] overflow-hidden" data-testid="slide-invitacion">
    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center shrink-0 mb-6">
      <p className="text-xs xl:text-sm uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-2">Bienvenido a este Manual</p>
      <h1 className="text-4xl sm:text-5xl xl:text-7xl font-bold text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
        Una <span className="italic text-[#C8A951]">Invitación</span>
      </h1>
      <div className="w-24 h-0.5 bg-[#C8A951] mx-auto mt-4" />
    </motion.div>

    <div className="flex-1 max-w-5xl mx-auto flex flex-col justify-center gap-5 min-h-0 overflow-hidden">
      <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}
        className="text-base xl:text-2xl leading-relaxed text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
        Hay vidas esperando ser alcanzadas, sueños esperando ser activados, y puertas esperando ser
        abiertas. Este manual no nació de una idea humana; nació de una <strong>convicción profética</strong>:
        que Dios quiere hacer algo nuevo, y lo hará a través de personas dispuestas a servir con
        excelencia.
      </motion.p>

      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }}
        className="p-5 xl:p-7 bg-gradient-to-r from-[#C8A951]/15 to-[#E2CF8A]/8 border-l-4 border-[#C8A951] rounded-r-lg">
        <p className="text-base xl:text-2xl italic text-[#1B2A4A] leading-relaxed" style={{ fontFamily: 'Spectral, serif' }}>
          "Donde no hay visión, el pueblo perece. Pero donde hay visión clara, hay dirección;
          donde hay orden, hay crecimiento; y donde hay propósito, hay multiplicación."
        </p>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
        <h3 className="text-xl xl:text-2xl font-bold text-[#1B2A4A] mb-3" style={{ fontFamily: 'Spectral, serif' }}>
          ¿Qué encontrarás aquí?
        </h3>
        <div className="grid grid-cols-2 xl:grid-cols-3 gap-2.5 xl:gap-3">
          {[
            ['El corazón del sistema', 'Visión, misión y valores'],
            ['Base bíblica sólida', 'Nehemías 3 y Tiempo 3'],
            ['Proceso claro', 'De persona a líder en 7 semanas'],
            ['Herramientas prácticas', 'Mentores, líderes y supervisores'],
            ['Estrategia de ganar', 'Metas concretas y medibles'],
          ].map(([t, d], i) => (
            <div key={i} className="flex items-start gap-2 p-2.5 xl:p-3 bg-white/60 border border-[#E7E2D6] rounded-lg">
              <div className="w-7 h-7 xl:w-9 xl:h-9 rounded-full bg-[#1B2A4A] text-[#C8A951] font-bold flex items-center justify-center shrink-0 text-xs xl:text-sm">{String(i + 1).padStart(2, '0')}</div>
              <div className="min-w-0">
                <p className="font-bold text-sm xl:text-base text-[#1B2A4A] leading-tight">{t}</p>
                <p className="text-[11px] xl:text-sm text-[#1B2A4A]/70 leading-snug">{d}</p>
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  </div>
);

// ============================================================
// SLIDE: ¿PARA QUIÉN? + PROMESA (página 4 del manual)
// ============================================================
export const SlideParaQuienPromesa = () => (
  <div className="h-full w-full flex flex-col px-8 xl:px-16 py-8 xl:py-10 bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] overflow-hidden" data-testid="slide-para-quien-promesa">
    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center shrink-0 mb-5">
      <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-1">Continuación</p>
      <h1 className="text-3xl sm:text-4xl xl:text-6xl font-bold text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
        ¿Para quién es <span className="italic text-[#C8A951]">este manual?</span>
      </h1>
      <div className="w-20 h-0.5 bg-[#C8A951] mx-auto mt-3" />
    </motion.div>

    <div className="flex-1 max-w-6xl mx-auto w-full flex flex-col gap-4 min-h-0 overflow-hidden">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}
        className="grid grid-cols-3 xl:grid-cols-6 gap-2 xl:gap-3">
        {[
          ['Pastor', 'Levantar equipo fuerte', '#1B2A4A'],
          ['Líder', 'Ver crecer a su gente', '#C8A951'],
          ['Mentor', 'Formar vidas', '#7C2D6F'],
          ['Servidor', 'Descubrir su puerta', '#0F766E'],
          ['Nuevo creyente', 'Proceso ordenado', '#B45309'],
          ['Supervisor', 'Coordinar movimiento', '#7E22CE'],
        ].map(([t, d, c], i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.06 }}
            className="p-3 xl:p-4 bg-white border-l-4 rounded-lg shadow-sm" style={{ borderLeftColor: c }}>
            <p className="font-bold text-sm xl:text-lg text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>{t}</p>
            <p className="text-[11px] xl:text-sm text-[#1B2A4A]/70 leading-snug mt-1">{d}</p>
          </motion.div>
        ))}
      </motion.div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
        className="flex-1 grid grid-cols-1 xl:grid-cols-2 gap-4 min-h-0">
        <div className="bg-white border border-[#E7E2D6] rounded-xl p-5 xl:p-7 shadow-sm">
          <p className="text-xs uppercase tracking-[0.25em] text-[#C8A951] font-bold mb-2">Cómo leerlo</p>
          <p className="text-sm xl:text-lg leading-relaxed text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
            No lo leas como un libro más. Léelo <strong>con lápiz en mano</strong>, con oración, con tu equipo
            al lado. Subraya lo que impacta. Marca lo que quieres implementar. Regresa a las secciones
            que te desafían. <em>Está diseñado para ser usado.</em>
          </p>
        </div>

        <div className="relative bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-xl p-5 xl:p-7 overflow-hidden shadow-md">
          <div className="absolute top-0 right-0 w-40 h-40 bg-[#C8A951]/10 rounded-full -mr-20 -mt-20" />
          <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-2 relative">Nuestra Promesa</p>
          <p className="text-sm xl:text-lg italic leading-relaxed relative" style={{ fontFamily: 'Spectral, serif' }}>
            Si aplicas con disciplina lo que aquí está escrito, <strong className="text-[#C8A951] not-italic">verás fruto</strong>.
            No porque este manual sea mágico, sino porque está alineado con los principios que Dios mismo
            estableció para edificar Su casa.
          </p>
          <div className="w-12 h-0.5 bg-[#C8A951] my-3 relative" />
          <p className="text-xs xl:text-sm text-white/80 relative">Hoy comienza algo nuevo. Gira la página.</p>
        </div>
      </motion.div>
    </div>
  </div>
);

// ============================================================
// SLIDE: PUERTA INDIVIDUAL (P1-P9) — usa LAS_9_PUERTAS[index]
// ============================================================
export const SlidePuertaIndividual = ({ slide }) => {
  const puerta = LAS_9_PUERTAS[slide.puertaIdx];
  if (!puerta) return null;
  const Icon = ICON_MAP[puerta.icon] || DoorOpen;

  return (
    <div className={`h-full w-full flex flex-col bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] overflow-hidden`} data-testid={`slide-puerta-${puerta.num}`}>
      {/* Header con color del ministerio */}
      <div className={`relative shrink-0 px-8 xl:px-12 py-5 xl:py-7 bg-gradient-to-r ${puerta.color} text-white overflow-hidden`}>
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -mr-32 -mt-32" />
        <div className="absolute bottom-0 left-0 w-32 h-32 bg-black/15 rounded-full -ml-16 -mb-16" />
        <div className="relative flex items-center gap-4 xl:gap-6">
          <div className="w-16 h-16 xl:w-24 xl:h-24 rounded-2xl bg-white/15 backdrop-blur-sm border-2 border-white/30 flex items-center justify-center shrink-0 shadow-lg">
            <Icon className="w-8 h-8 xl:w-12 xl:h-12 text-white drop-shadow-lg" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[10px] xl:text-sm uppercase tracking-[0.3em] font-bold opacity-90">Puerta {puerta.num}</p>
            <h1 className="text-2xl sm:text-3xl xl:text-5xl font-bold leading-tight drop-shadow" style={{ fontFamily: 'Spectral, serif' }}>
              {puerta.nombre}
            </h1>
            {puerta.resumen && (
              <p className="text-sm xl:text-lg italic opacity-90 mt-1" style={{ fontFamily: 'Spectral, serif' }}>
                {puerta.resumen}
              </p>
            )}
          </div>
          <div className="hidden md:flex shrink-0 w-20 h-20 xl:w-28 xl:h-28 rounded-full bg-white text-[#1B2A4A] items-center justify-center shadow-2xl ring-4 ring-white/30">
            <span className="font-black" style={{ fontFamily: 'Spectral, serif', fontSize: 'clamp(28px, 3.5vw, 56px)' }}>{puerta.num}</span>
          </div>
        </div>
      </div>

      {/* Contenido */}
      <div className="flex-1 min-h-0 overflow-y-auto px-8 xl:px-12 py-5 xl:py-7">
        {puerta.nehemias && (
          <p className="text-sm xl:text-base italic font-semibold mb-3" style={{ color: puerta.accent }}>
            📖 {puerta.nehemias}
          </p>
        )}

        <div className="p-4 xl:p-5 bg-white border-l-4 rounded-r-lg shadow-sm mb-4" style={{ borderLeftColor: puerta.accent }}>
          <p className="text-[10px] xl:text-xs uppercase tracking-widest font-bold mb-1.5" style={{ color: puerta.accent }}>Propósito</p>
          <p className="text-sm xl:text-lg leading-relaxed text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
            {puerta.proposito}
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 xl:gap-4">
          {puerta.funciones && <PuertaListBlock titulo="Funciones" items={puerta.funciones} accent={puerta.accent} />}
          {puerta.responsabilidades && <PuertaListBlock titulo="Responsabilidades" items={puerta.responsabilidades} accent={puerta.accent} />}
          {puerta.actividades && <PuertaListBlock titulo="Actividades" items={puerta.actividades} accent={puerta.accent} />}
          {puerta.proceso && <PuertaListBlock titulo="Proceso" items={puerta.proceso} accent={puerta.accent} />}
          {puerta.bienvenida && <PuertaListBlock titulo="Proceso de Bienvenida" items={puerta.bienvenida} accent={puerta.accent} />}
          {puerta.estructura && <PuertaListBlock titulo="Estructura" items={puerta.estructura} accent={puerta.accent} />}
          {puerta.indicadores && <PuertaListBlock titulo="Indicadores de Éxito" items={puerta.indicadores} accent={puerta.accent} />}
        </div>

        {puerta.ministerios && (
          <div className="mt-4">
            <p className="text-[10px] xl:text-xs uppercase tracking-widest font-bold mb-2" style={{ color: puerta.accent }}>Ministerios de Apoyo</p>
            <div className="flex flex-wrap gap-2">
              {puerta.ministerios.map(m => (
                <span key={m} className="px-3 py-1 text-white text-xs xl:text-sm rounded-full font-medium shadow" style={{ backgroundColor: puerta.accent }}>
                  {m}
                </span>
              ))}
            </div>
          </div>
        )}

        {puerta.tiempo && (
          <div className="mt-4 p-3 xl:p-4 rounded-lg text-sm xl:text-base italic font-medium" style={{ backgroundColor: `${puerta.accent}20`, border: `1px solid ${puerta.accent}66` }}>
            ⏱ {puerta.tiempo}
          </div>
        )}
      </div>
    </div>
  );
};

const PuertaListBlock = ({ titulo, items, accent }) => (
  <div className="bg-white border border-[#E7E2D6] rounded-lg p-3 xl:p-4 shadow-sm">
    <p className="text-[10px] xl:text-xs uppercase tracking-widest font-bold mb-2" style={{ color: accent }}>{titulo}</p>
    <ul className="space-y-1">
      {items.map((it, i) => (
        <li key={i} className="flex items-start gap-2 text-sm xl:text-base text-[#1B2A4A] leading-snug">
          <span className="font-bold mt-0.5 shrink-0" style={{ color: accent }}>•</span>
          <span>{it}</span>
        </li>
      ))}
    </ul>
  </div>
);

// ============================================================
// SLIDE: DISCIPULADO EN 8 SEMANAS (página 25 del manual)
// ============================================================
const DISCIPULADO_8 = [
  ['S1', 'Salvación y seguridad en Cristo', '2 Corintios 5:17 · Ser nueva criatura'],
  ['S2', 'Oración y relación con Dios', 'Jeremías 33:3 · Aprender a hablar con Él'],
  ['S3', 'La Biblia y crecimiento espiritual', 'El alimento diario del alma'],
  ['S4', 'La iglesia y congregarse', 'No somos piedras sueltas, somos familia'],
  ['S5', 'Cambio de vida y santidad', 'El evangelio transforma lo práctico'],
  ['S6', 'Visión y propósito', 'Descubrir para qué fuimos creados'],
  ['S7', 'Descubrir el don', 'Servir en una puerta'],
  ['S8', 'Preparación para el liderazgo', 'De discípulo a formador'],
];

export const SlideDiscipulado8 = () => (
  <div className="h-full w-full flex flex-col px-8 xl:px-12 py-6 xl:py-9 bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] overflow-hidden" data-testid="slide-discipulado-8">
    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="text-center shrink-0 mb-5">
      <div className="inline-flex items-center gap-1.5 bg-[#1B2A4A] text-white rounded-full px-3 py-1 mb-2 font-bold text-[10px] xl:text-xs uppercase tracking-widest">
        <BookOpen className="w-3 h-3" /> Mapa del Nuevo Creyente
      </div>
      <h2 className="text-3xl sm:text-4xl xl:text-6xl font-bold text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
        Discipulado en <span className="text-[#C8A951]">8 Semanas</span>
      </h2>
      <p className="text-xs xl:text-base text-muted-foreground mt-1">
        Las primeras 8 semanas son decisivas — determinan si el nuevo creyente se queda o se pierde.
      </p>
    </motion.div>

    <div className="flex-1 grid grid-cols-2 xl:grid-cols-4 gap-2.5 xl:gap-3 min-h-0 max-w-[1700px] mx-auto w-full">
      {DISCIPULADO_8.map(([s, t, d], i) => (
        <motion.div key={s} initial={{ opacity: 0, y: 18, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ delay: 0.05 + i * 0.05, type: 'spring', stiffness: 95 }}
          className="bg-white border-2 border-[#E7E2D6] rounded-xl p-3 xl:p-4 shadow-sm flex items-start gap-3 hover:border-[#C8A951]/60 transition-colors">
          <div className="w-12 h-12 xl:w-16 xl:h-16 rounded-lg bg-gradient-to-br from-[#C8A951] to-[#A37C2C] text-white font-black flex items-center justify-center shrink-0 shadow-md" style={{ fontFamily: 'Spectral, serif', fontSize: 'clamp(16px, 1.8vw, 28px)' }}>
            {s}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-bold text-sm xl:text-lg text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>{t}</p>
            <p className="text-[11px] xl:text-sm text-[#1B2A4A]/65 leading-snug mt-0.5">{d}</p>
          </div>
        </motion.div>
      ))}
    </div>
  </div>
);

// ============================================================
// Renderer central
// ============================================================
export const SlideRenderer = ({ slide }) => {
  if (!slide) return null;
  switch (slide.type) {
    case 'portada': return <SlidePortada slide={slide} />;
    case 'indice': return <SlideIndice />;
    case 'invitacion': return <SlideInvitacion />;
    case 'para-quien-promesa': return <SlideParaQuienPromesa />;
    case 'intro-manual': return <SlideIntroManual />;
    case 'identidad': return <SlideIdentidad />;
    case 'lema-nehemias': return <SlideLemaNehemias />;
    case 'ley-7-semanas': return <SlideLey7Semanas />;
    case 'modelo-cap': return <SlideModeloCAP />;
    case 'operacion-72': return <SlideOperacion72 />;
    case 'las-9-puertas': return <SlideLas9Puertas />;
    case 'puerta-individual': return <SlidePuertaIndividual slide={slide} />;
    case 'estructura': return <SlideEstructura />;
    case 'lider': return <SlideLider />;
    case 'mentor': return <SlideMentor />;
    case 'discipulado-8': return <SlideDiscipulado8 />;
    case 'estrategia': return <SlideEstrategia />;
    case 'consolidado': return <SlideConsolidado />;
    case 'reunion': return <SlideReunionSupervisores />;
    case 'cierre': return <SlideCierre />;
    default: return <div className="p-10 text-center">Slide: {slide.id}</div>;
  }
};
