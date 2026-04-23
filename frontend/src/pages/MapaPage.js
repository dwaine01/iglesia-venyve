import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ArrowRight, Flame, Target, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

const MAP_IMG_1 = 'https://customer-assets.emergentagent.com/job_76fb7cc6-0227-4846-942d-ba7af44fd075/artifacts/kz83xom5_ChatGPT%20Image%20Apr%2022%2C%202026%2C%2012_06_51%20AM.png';

const weeks = [
  { num: 1, name: 'Preparacion / Oracion Profetica', tag: 'Organizacion', color: 'bg-emerald-500', hoverColor: 'hover:border-emerald-400', desc: 'Elaborar lista de 30 personas. Campana de oracion de 6am-9am. Salir a tocar puertas. Semana de GANAR.', emoji: 'Flame' },
  { num: 2, name: 'Invasion (NPT)', tag: 'Contactados', color: 'bg-blue-500', hoverColor: 'hover:border-blue-400', desc: 'Entregar MCD. Visitar diariamente. Consolidar en 72 horas. Batalla contra los 7 espiritus peores.' },
  { num: 3, name: 'MCD', tag: 'Asistencia', color: 'bg-cyan-500', hoverColor: 'hover:border-cyan-400', desc: 'Ayunos intensos. Visitas diarias. Graduacion con certificados NPT. Introducir LBS.' },
  { num: 4, name: 'Liberacion (LBS 1)', tag: 'LBS 1', color: 'bg-orange-500', hoverColor: 'hover:border-orange-400', desc: 'Liberacion por capas: Persona, Casa, Tierra. Romper lineas de iniquidad. Cuestionarios espirituales.' },
  { num: 5, name: 'Bendicion (LBS 2)', tag: 'LBS 2', color: 'bg-yellow-500', hoverColor: 'hover:border-yellow-400', desc: 'Llenar 4 areas: Corazon, Alma, Mente, Cuerpo. Llenura del Espiritu Santo. Consolidacion.' },
  { num: 6, name: 'Sanidad (LBS 3)', tag: 'LBS 3', color: 'bg-purple-500', hoverColor: 'hover:border-purple-400', desc: 'Sanidad espiritual: afan, ansiedad, amargura, falta de perdon. Curar el corazon del dolor.' },
  { num: 7, name: 'Retiro + Cierre', tag: 'Retiro', color: 'bg-red-500', hoverColor: 'hover:border-red-400', desc: 'Retiro espiritual. Encuentro con el Espiritu Santo. Graduacion con Mi Llamado y Vision Familiar.' },
];

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06, delayChildren: 0.2 } },
};
const itemVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease: 'easeOut' } },
};

export default function MapaPage() {
  const navigate = useNavigate();

  return (
    <div className="px-3 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-10 space-y-6 sm:space-y-8 max-w-6xl mx-auto">
      {/* Motivational Hero */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: 'easeOut' }}>
        <div className="relative rounded-2xl bg-[#1B2A4A] p-6 sm:p-8 lg:p-10 overflow-hidden">
          <div className="absolute inset-0 animated-dots opacity-20"></div>
          <div className="absolute top-0 right-0 w-1/2 h-full bg-gradient-to-l from-[#C8A951]/5 to-transparent"></div>
          <div className="relative z-10">
            <div className="flex items-center gap-2 mb-3">
              <motion.div animate={{ rotate: [0, 15, -15, 0] }} transition={{ duration: 3, repeat: Infinity }}>
                <Target className="w-6 h-6 text-[#C8A951]" />
              </motion.div>
              <Badge className="bg-[#C8A951]/20 text-[#C8A951] border-[#C8A951]/30 text-xs">Estrategia de Transformacion</Badge>
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-3" style={{ fontFamily: 'Spectral, serif' }}>
              Mapa de las <span className="shimmer-text">7 Semanas</span>
            </h1>
            <p className="text-white/60 max-w-xl text-sm leading-relaxed">
              7 semanas de crecimiento y formacion intencional. Cada semana representa un avance hacia la consolidacion total del individuo.
            </p>
            <div className="flex flex-wrap items-center gap-3 mt-6">
              <motion.div animate={{ scale: [1, 1.05, 1] }} transition={{ duration: 2, repeat: Infinity }} className="flex items-center gap-1.5 bg-white/10 px-3 py-1.5 rounded-full text-sm text-white/80">
                <Flame className="w-3.5 h-3.5 text-[#C8A951]" /> Crecimiento Intencional
              </motion.div>
              <div className="flex items-center gap-1.5 bg-white/10 px-3 py-1.5 rounded-full text-sm text-white/80">
                <Sparkles className="w-3.5 h-3.5 text-[#1FA6A0]" /> Proceso Progresivo
              </div>
              <div className="flex items-center gap-1.5 bg-white/10 px-3 py-1.5 rounded-full text-sm text-white/80">
                <Target className="w-3.5 h-3.5 text-[#C8A951]" /> Impacto Duradero
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Infographic Image with glow effect */}
      <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, delay: 0.15 }}>
        <Card className="overflow-hidden shadow-lg border-2 border-[hsl(43,52%,55%)]/20 hover:shadow-2xl hover:border-[hsl(43,52%,55%)]/40 transition-all duration-500">
          <CardContent className="p-0 relative">
            <img src={MAP_IMG_1} alt="Mapa La Ley de las 7 Semanas" className="w-full h-auto" data-testid="map-infographic-1" />
            <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-black/30 to-transparent flex items-end p-4">
              <p className="text-white text-xs font-medium opacity-80">De Persona a Discipulo, de Discipulo a Obrero, de Obrero a Lider o Ministro</p>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Motivational Quote Banner */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.4, delay: 0.25 }}
        className="flex items-center gap-4 bg-gradient-to-r from-[#C8A951]/10 via-transparent to-[#1FA6A0]/10 rounded-xl p-5 border border-[#C8A951]/20"
      >
        <motion.div animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 2, repeat: Infinity }} className="shrink-0">
          <div className="w-12 h-12 rounded-full bg-[#C8A951]/15 flex items-center justify-center">
            <Flame className="w-6 h-6 text-[#C8A951]" />
          </div>
        </motion.div>
        <div>
          <p className="text-sm font-semibold text-foreground" style={{ fontFamily: 'Spectral, serif' }}>
            "Si ustedes hacen caso a Dios y se guian por esto, van a desembocar una gloria."
          </p>
          <p className="text-xs text-muted-foreground mt-1">Si cuidas la planta, le echas agua y la proteges, va a dar fruto.</p>
        </div>
      </motion.div>

      {/* Interactive Week Cards */}
      <div>
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="text-xl font-bold mb-5 gradient-underline inline-block" style={{ fontFamily: 'Spectral, serif' }}
        >
          Navegar por Semana
        </motion.h2>
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
        >
          {weeks.map((week) => (
            <motion.div key={week.num} variants={itemVariants} whileHover={{ y: -8, scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Card
                className={`week-card-hover cursor-pointer h-full border-2 border-transparent ${week.hoverColor} transition-all duration-300`}
                onClick={() => navigate(`/semana/${week.num}`)}
                data-testid={`map-week-hotspot-${week.num}`}
              >
                <CardContent className="p-5 flex flex-col h-full">
                  <div className="flex items-center gap-2 mb-3">
                    <motion.div
                      whileHover={{ rotate: 10, scale: 1.1 }}
                      className={`w-10 h-10 rounded-xl ${week.color} flex items-center justify-center text-white text-sm font-bold shadow-md`}
                    >
                      {week.num}
                    </motion.div>
                    <Badge variant="outline" className="text-xs">{week.tag}</Badge>
                  </div>
                  <h3 className="font-bold text-sm mb-2" style={{ fontFamily: 'Spectral, serif' }}>
                    Semana {week.num}: {week.name}
                  </h3>
                  <p className="text-xs text-muted-foreground leading-relaxed flex-1">{week.desc}</p>
                  <div className="flex items-center gap-1 text-xs text-[#C8A951] mt-4 font-semibold group">
                    Ver detalles
                    <motion.div whileHover={{ x: 6 }} className="inline-flex">
                      <ArrowRight className="w-3.5 h-3.5" />
                    </motion.div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* Animated Process Flow */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.5 }}>
        <Card className="bg-[#1B2A4A] text-white border-0 overflow-hidden relative">
          <div className="absolute inset-0 animated-dots opacity-15"></div>
          <CardContent className="p-6 sm:p-8 relative z-10">
            <div className="flex items-center gap-2 mb-4">
              <motion.div animate={{ rotate: 360 }} transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}>
                <Target className="w-5 h-5 text-[#C8A951]" />
              </motion.div>
              <h3 className="text-[#C8A951] font-bold text-lg" style={{ fontFamily: 'Spectral, serif' }}>Flujo del Proceso</h3>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              {['Ganar Almas', 'Hijos Discipulos', 'Obreros'].map((step, idx) => (
                <React.Fragment key={idx}>
                  <motion.span
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.6 + idx * 0.15 }}
                    className="bg-white/10 px-4 py-2 rounded-lg border border-white/5 hover:bg-white/15 transition-colors cursor-default"
                  >
                    {step}
                  </motion.span>
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 + idx * 0.15 }}>
                    <ArrowRight className="w-4 h-4 text-[#C8A951]" />
                  </motion.div>
                </React.Fragment>
              ))}
              <motion.span
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 1.1, type: 'spring', stiffness: 200 }}
                className="bg-[#C8A951]/20 px-4 py-2 rounded-lg text-[#C8A951] font-bold border border-[#C8A951]/30 pulse-gold"
              >
                Ministros
              </motion.span>
            </div>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.2 }}
              className="text-white/50 text-xs mt-5 leading-relaxed max-w-2xl"
            >
              Ley de 30-60-100: De cada 30 personas impactadas, minimo 10 responderan (30%). Si son 30 obreros impactando 30 casas cada uno = 900 casas. Al 30% = 300 casas. De esas 300, 100 casas concretas = 100 grupos pequenos.
            </motion.p>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
