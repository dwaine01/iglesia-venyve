import React from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Separator } from '../components/ui/separator';
import { Badge } from '../components/ui/badge';
import { Target, Infinity, Heart, Zap, Shield, Users, ArrowRight, BookOpen, Flame, Sparkles, Star } from 'lucide-react';
import { motion } from 'framer-motion';

const INTRO_IMG = 'https://customer-assets.emergentagent.com/job_76fb7cc6-0227-4846-942d-ba7af44fd075/artifacts/jibur5mh_ChatGPT%20Image%20Apr%2021%2C%202026%2C%2011_54_17%20PM.png';
const LOGO_URL = 'https://customer-assets.emergentagent.com/job_cool-kare-8/artifacts/qj9ur7op_logo%20casa%20e%20oracion%20ven%20y%20ve.png';

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.15 } },
};
const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
};

export default function IntroduccionPage() {
  return (
    <div className="px-3 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-10 space-y-6 sm:space-y-8 max-w-5xl mx-auto">
      {/* Hero */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <div className="relative rounded-2xl overflow-hidden bg-[#1B2A4A] p-6 sm:p-10">
          <div className="absolute inset-0 animated-dots opacity-15"></div>
          <div className="absolute top-0 right-0 w-1/2 h-full bg-gradient-to-l from-[#C8A951]/8 to-transparent"></div>
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-5">
              <motion.img
                src={LOGO_URL} alt="" className="w-14 h-14 object-contain"
                animate={{ rotate: [0, 5, -5, 0] }}
                transition={{ duration: 4, repeat: Infinity }}
              />
              <Badge className="bg-[#C8A951]/20 text-[#C8A951] border-[#C8A951]/30">Manual Corporativo</Badge>
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-3" style={{ fontFamily: 'Spectral, serif' }}>
              Introduccion del <span className="shimmer-text">Manual</span>
            </h1>
            <h2 className="text-lg text-white/70 mb-2" style={{ fontFamily: 'Spectral, serif' }}>
              La Ley de las 7 Semanas
            </h2>
            <p className="text-white/50 text-sm">Un Proceso de Crecimiento y Formacion</p>
            <div className="flex flex-wrap gap-3 mt-6">
              {['Crecimiento Intencional', 'Proceso Progresivo', 'Impacto Duradero'].map((tag, i) => (
                <motion.span
                  key={i}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.4 + i * 0.1 }}
                  className="bg-white/10 px-3 py-1.5 rounded-full text-xs text-white/70 border border-white/5"
                >
                  {tag}
                </motion.span>
              ))}
            </div>
          </div>
          <div className="absolute top-0 right-0 w-1/3 h-full opacity-10">
            <img src={INTRO_IMG} alt="" className="w-full h-full object-cover" />
          </div>
        </div>
      </motion.div>

      {/* Motivational Banner */}
      <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4, delay: 0.2 }}>
        <div className="flex items-center gap-4 bg-gradient-to-r from-[#C8A951]/10 via-transparent to-[#1FA6A0]/10 rounded-xl p-5 border border-[#C8A951]/20">
          <motion.div animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 2, repeat: Infinity }} className="shrink-0">
            <div className="w-12 h-12 rounded-full bg-[#C8A951]/15 flex items-center justify-center">
              <Flame className="w-6 h-6 text-[#C8A951]" />
            </div>
          </motion.div>
          <p className="text-sm font-medium text-foreground italic">
            "Mas que un programa, este sistema es una <strong className="text-[#C8A951]">estrategia de transformacion</strong> donde cada semana representa un avance intencional."
          </p>
        </div>
      </motion.div>

      {/* Intro Text */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.15 }}>
        <Card className="hover:shadow-md transition-shadow duration-300">
          <CardContent className="p-6 sm:p-8">
            <div className="reading-content">
              <p className="text-base leading-7 text-foreground">
                Este manual ha sido disenado como una guia practica, estrategica y espiritual para la implementacion
                efectiva de la Ley de las 7 Semanas, un modelo comprobado de crecimiento, consolidacion y formacion
                integral dentro de la vision.
              </p>
              <p className="text-base leading-7 text-foreground mt-4">
                La base de este proyecto no es simplemente una actividad religiosa, sino un proceso estructurado,
                intencional y continuo, enfocado en producir resultados reales y medibles. Como se establece en la
                ensenanza original: <strong className="text-[#1B2A4A]">la vision no es abstracta, es concreta; y lo concreto produce resultados.</strong>
              </p>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* The Infographic Image */}
      <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, delay: 0.2 }}>
        <Card className="overflow-hidden hover:shadow-lg transition-shadow duration-500">
          <CardContent className="p-0">
            <img
              src={INTRO_IMG}
              alt="Introduccion del Manual - La Ley de las 7 Semanas"
              className="w-full h-auto"
              data-testid="intro-infographic-image"
            />
          </CardContent>
        </Card>
      </motion.div>

      {/* The Vision Process - Animated */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.25 }}>
        <Card className="hover:shadow-md transition-shadow duration-300">
          <CardContent className="p-6 sm:p-8">
            <div className="flex items-center gap-2 mb-4">
              <motion.div animate={{ rotate: 360 }} transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}>
                <Target className="w-5 h-5 text-[#C8A951]" />
              </motion.div>
              <h3 className="text-xl font-semibold" style={{ fontFamily: 'Spectral, serif' }}>El Sistema Progresivo</h3>
            </div>
            <p className="text-muted-foreground mb-6 reading-content">
              A lo largo de este manual, se presenta un sistema progresivo que transforma personas desde su estado
              inicial hasta su desarrollo como individuos firmes, formados y comprometidos:
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-8 py-6">
              {[
                { label: 'De Persona', sublabel: 'a Discipulo', color: 'bg-[#1B2A4A]', icon: Users },
                { label: 'De Discipulo', sublabel: 'a Obrero', color: 'bg-[#C8A951]', icon: Shield },
                { label: 'De Obrero', sublabel: 'a Lider/Ministro', color: 'bg-[#1FA6A0]', icon: Target },
              ].map((step, idx) => (
                <React.Fragment key={idx}>
                  <motion.div
                    className="flex flex-col items-center text-center"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 + idx * 0.2 }}
                    whileHover={{ scale: 1.1, y: -4 }}
                  >
                    <motion.div
                      className={`w-16 h-16 rounded-full ${step.color} flex items-center justify-center text-white mb-3 shadow-lg`}
                      animate={{ boxShadow: ['0 4px 14px rgba(0,0,0,0.1)', '0 8px 25px rgba(0,0,0,0.2)', '0 4px 14px rgba(0,0,0,0.1)'] }}
                      transition={{ duration: 3, repeat: Infinity }}
                    >
                      <step.icon className="w-7 h-7" />
                    </motion.div>
                    <p className="font-bold text-sm">{step.label}</p>
                    <p className="text-xs text-muted-foreground">{step.sublabel}</p>
                  </motion.div>
                  {idx < 2 && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 + idx * 0.2 }}>
                      <ArrowRight className="w-6 h-6 text-[#C8A951] hidden sm:block" />
                    </motion.div>
                  )}
                </React.Fragment>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      <Separator />

      {/* Key Principles - Animated Grid */}
      <div>
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="flex items-center gap-2 mb-5">
          <Star className="w-5 h-5 text-[#C8A951]" />
          <h3 className="text-xl font-bold gradient-underline inline-block" style={{ fontFamily: 'Spectral, serif' }}>
            Principios Clave de la Ley de las 7 Semanas
          </h3>
        </motion.div>
        <motion.div variants={containerVariants} initial="hidden" animate="visible" className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[
            { icon: Infinity, text: 'La importancia de los procesos continuos', desc: 'Sin proceso continuo, las personas caen en vacios espirituales que generan opresion y perdida.' },
            { icon: Heart, text: 'La necesidad de eliminar vacios espirituales', desc: 'Los vacios llevan a la gente a opresiones, complejos, y dependencias que desgastan a los pastores.' },
            { icon: Zap, text: 'El enfoque en la accion, no solo en la teoria', desc: 'La vision es tu negocio. Quieres resultados concretos, no actividades abstractas sin proposito.' },
            { icon: Shield, text: 'La disciplina en la ejecucion', desc: 'Como la hormiga: sabe lo que quiere, cuando lo quiere y donde lo quiere. Organizacion por trimestre.' },
            { icon: Users, text: 'El trabajo en equipo con un mismo objetivo', desc: 'Todo el mundo tiene que estar hablando lo mismo. Una explosion de esfuerzo coordinado.' },
          ].map((principle, idx) => (
            <motion.div key={idx} variants={itemVariants} whileHover={{ y: -4, scale: 1.01 }}>
              <Card className="week-card-hover h-full">
                <CardContent className="p-5 flex gap-4">
                  <motion.div
                    whileHover={{ rotate: 15, scale: 1.1 }}
                    className="w-11 h-11 rounded-xl bg-[#C8A951]/10 flex items-center justify-center shrink-0"
                  >
                    <principle.icon className="w-5 h-5 text-[#C8A951]" />
                  </motion.div>
                  <div>
                    <p className="font-semibold text-sm mb-1">{principle.text}</p>
                    <p className="text-xs text-muted-foreground leading-relaxed">{principle.desc}</p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </div>

      <Separator />

      {/* Purpose - Enhanced */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.35 }}>
        <Card className="bg-[#1B2A4A] text-white border-0 overflow-hidden relative">
          <div className="absolute inset-0 animated-dots opacity-15"></div>
          <CardContent className="p-6 sm:p-8 relative z-10">
            <div className="flex items-center gap-2 mb-5">
              <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 2, repeat: Infinity }}>
                <BookOpen className="w-6 h-6 text-[#C8A951]" />
              </motion.div>
              <h3 className="text-xl font-bold text-[#C8A951]" style={{ fontFamily: 'Spectral, serif' }}>Este Manual Tiene Como Proposito</h3>
            </div>
            <div className="space-y-3">
              {[
                'Facilitar la comprension del proceso completo',
                'Guiar paso a paso la implementacion del modelo',
                'Alinear equipos bajo una misma vision',
                'Garantizar resultados consistentes y sostenibles',
              ].map((item, idx) => (
                <motion.li
                  key={idx}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 + idx * 0.1 }}
                  className="flex items-start gap-3 list-none"
                >
                  <motion.div
                    whileHover={{ scale: 1.2 }}
                    className="w-6 h-6 rounded-full bg-[#1FA6A0] flex items-center justify-center shrink-0 mt-0.5"
                  >
                    <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                  </motion.div>
                  <span className="text-white/90 text-sm">{item}</span>
                </motion.li>
              ))}
            </div>
            <Separator className="my-6 bg-white/10" />
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.9 }}
              className="text-white/70 text-sm leading-relaxed italic"
            >
              Si se sigue con disciplina, unidad y compromiso, este proceso no solo producira crecimiento,
              sino tambien <strong className="text-[#C8A951] glow-text">IMPACTO REAL Y DURADERO.</strong>
            </motion.p>
          </CardContent>
        </Card>
      </motion.div>

      {/* Footer */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1 }} className="text-center text-sm text-muted-foreground pb-6">
        <Sparkles className="w-4 h-4 inline-block text-[#C8A951] mr-1" />
        <span>Casa de Oracion Ven y Ve &mdash; Primera Iglesia del Nazareno</span>
        <p className="mt-1">Pastora Carmen Garcia</p>
      </motion.div>
    </div>
  );
}
