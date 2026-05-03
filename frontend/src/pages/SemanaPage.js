import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Checkbox } from '../components/ui/checkbox';
import { Progress } from '../components/ui/progress';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import { ChevronLeft, ChevronRight, Save, Flame, CheckCircle2, Trophy, Target, BookOpen, Home, Users, Heart, Star, UserCircle, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';

const WEEK_MOTIVATIONS = {
  1: '"Todo el mundo tiene que estar hablando lo mismo: GANAR, GANAR, GANAR."',
  2: '"Esta semana es de invasión. Sal a tocar puertas. Contacta a tu lista de 30."',
  3: '"Mi Conexión con Dios. Que confiesen las oraciones todos los días."',
  4: '"NPT - 3 días que cambian una vida. Si no lo consolidas en 72 horas, ya lo perdiste."',
  5: '"Si liberas la persona pero no rompes la tierra, más temprano que tarde te va a fallar."',
  6: '"Cuando el espíritu impuro sale, la casa queda vacía. Hay que llenarla."',
  7: '"Sanar el corazón del dolor es la clave para prevenir la recaída."',
};

const WEEK_ICONS = {
  1: Star, 2: Target, 3: BookOpen, 4: Flame, 5: Heart, 6: Star, 7: Trophy,
};

const WEEK_CONTENT = {
  1: {
    title: 'Preparación / Oración Profética',
    subtitle: 'Organización - Semana de GANAR',
    color: 'from-emerald-500 to-emerald-700',
    solidColor: 'bg-emerald-500',
    tag: 'Organización',
    intro: 'La primera semana es la semana de organizarse para ganar. Todo el mundo, la primera semana, tiene que tener su lista de treinta personas con familiares, amigos y conocidos. Esta semana entera es de ganar.',
    sections: [
      { title: 'La Ley de la Hormiga', content: 'La primera semana se trabaja con la ley de la hormiga. La hormiga sabe lo que quiere, cuando lo quiere y donde lo quiere. En tres meses, la hormiga consigue toda la comida de un ano. Si nos organizamos por trimestre, en un trimestre podemos recoger toda la cosecha de un ano.' },
      { title: 'Como Comenzar', content: 'Se escoge un equipo y se hace una campana para inaugurar la semana de ganados. A las seis de la manana se reunen en el templo y se ora de seis a nueve. Orar con la lista en el pecho, pidiendo a Dios que rompa fortalezas. A las nueve de la manana, todos a la calle a tocar puertas.' },
      { title: 'Estrategia de Campo', content: 'Cada persona debe visitar a los familiares, amigos, companeros de trabajo, personas que estan divorciandose, que tienen familiares en la carcel, enfermos, sin trabajo. Toda persona con necesidad responde al ministerio. Se visita desde las 9am hasta las 6-7pm.' },
      { title: 'Ley del 30-60-100', content: 'De cada 30 personas que impactes, lo minimo que te van a quedar son 10 (30%). Si son 30 obreros, cada uno impactando 30 casas = 900 casas. Al 30% = 300 casas. De esas 300, te quedan 100 casas concretas, 100 grupos pequenos.' },
      { title: 'Ambiente de Victoria', content: 'Decorar la iglesia con esloganes: GANAR, GANAR, GANAR. Mandar mensajes cada 3 horas a la gente: ganar, ganar, ganar. Notas de voz, todo el mundo hablando de lo mismo. Es una explosion de esfuerzo coordinado.' },
    ]
  },
  2: {
    title: 'Invasión',
    subtitle: 'Contactados - Salir a las Calles',
    color: 'from-blue-500 to-blue-700',
    solidColor: 'bg-blue-500',
    tag: 'Contactados',
    intro: 'La semana de invasión es cuando sales a contactar directamente a las personas. Es tocar puertas, hacer llamadas, visitar casas. El objetivo es que las personas de tu lista respondan positivamente al llamado.',
    sections: [
      { title: 'Salir a la Calle', content: 'Esta semana es de acción. No es tiempo de planear, es tiempo de ejecutar. Tocar puertas, visitar casas, hacer llamadas. Cada obrero debe contactar a su lista de 30 personas.' },
      { title: 'Estrategia de Contacto', content: 'Visitar en horarios estratégicos. Llevar material de la iglesia. Invitar a eventos, a la macrocélula, al servicio dominical. El objetivo es establecer el primer contacto real y generar interés.' },
      { title: 'Registro de Respuestas', content: 'Anotar quién respondió positivamente, quién mostró interés, quién necesita más oración. Este registro es clave para el seguimiento de las próximas semanas.' },
      { title: 'Guerra Espiritual', content: 'Durante la invasión, el enemigo se manifiesta. Hay resistencia, puertas que no se abren, personas que rechazan. Por eso la oración y la guerra espiritual son esenciales cada día de esta semana.' },
    ]
  },
  3: {
    title: 'MCD - Mi Conexión con Dios',
    subtitle: 'Asistencia - Conectar con Dios',
    color: 'from-cyan-500 to-cyan-700',
    solidColor: 'bg-cyan-500',
    tag: 'Asistencia',
    intro: 'Esta semana se entrega el libro MCD (Mi Conexión con Dios). Es una semana de asistencia diaria, de hacer que la persona lea, confiese y se conecte con Dios a través de las oraciones del libro.',
    sections: [
      { title: 'Entrega del Libro MCD', content: 'Se entrega el libro Mi Conexión con Dios a cada persona que respondió positivamente. Este libro tiene oraciones poderosas que la persona debe confesar diariamente.' },
      { title: 'Seguimiento Diario', content: 'Visitar todos los días. Llamar por teléfono. Enviar mensajes de WhatsApp. Asegurarse de que la persona esté leyendo y confesando las oraciones. Si no saben leer, grabar las oraciones y enviarlas por audio.' },
      { title: 'Ayunos y Oración', content: 'Esta semana se aprietan los ayunos. Los líderes y obreros ayunan para que Dios rompa las resistencias y las personas se consoliden firmemente.' },
      { title: 'Introducir NPT', content: 'Al finalizar esta semana, se introduce el libro NPT (Nací Para Triunfar). Se les dice: "La próxima semana vamos a trabajar un libro de 3 días que cambiará tu vida."' },
    ]
  },
  4: {
    title: 'Nací Para Triunfar (NPT)',
    subtitle: 'Transformación - Libro de 3 Días',
    color: 'from-amber-500 to-orange-600',
    solidColor: 'bg-amber-500',
    tag: 'NPT',
    intro: 'NPT es un libro de 3 días. Es intenso, poderoso, transformador. En esta semana se trabaja este libro con las personas que han respondido. Al final de la semana hay graduación.',
    sections: [
      { title: 'Trabajo de 3 Días', content: 'NPT no es un libro que se lee en semanas. Son 3 días intensos donde la persona confiesa, declara, rompe ataduras y nace para triunfar. Es un proceso acelerado de transformación.' },
      { title: 'Las 72 Horas Críticas', content: 'El Espíritu Santo dijo: Si no lo consolidas en tres días, ya lo perdiste. Por eso NPT es de 3 días. Porque en esas 72 horas se define si la persona se queda o si el enemigo la recupera.' },
      { title: 'Los 7 Espíritus Peores', content: 'Esta es la semana más violenta espiritualmente. Se manifiestan los 7 espíritus peores. La familia se burla, las tentaciones se multiplican, el enemigo ataca con todo. Por eso la consolidación debe ser agresiva y firme.' },
      { title: 'Graduación NPT', content: 'Al final de esta semana se hace la ceremonia de graduación. Se entregan diplomas enmarcados con el sello de la iglesia. Se crea identidad: "Yo soy de Ven y Ve, nací para triunfar."' },
      { title: 'Introducir LBS', content: 'En la noche de graduación se introduce el libro LBS. Se dice: "Las próximas tres semanas vamos a trabajar Liberación, Bendición y Sanidad. Son 3 semanas que te van a cambiar completamente."' },
    ]
  },
  5: {
    title: 'Liberación (LBS 1)',
    subtitle: 'Rompiendo Cadenas - 3 Áreas',
    color: 'from-orange-500 to-red-600',
    solidColor: 'bg-orange-500',
    tag: 'LBS 1',
    intro: 'La primera parte de LBS es Liberación. Se trabajan las tres áreas donde se esconden los demonios: la Persona, la Casa y la Tierra. Si no liberas las tres áreas, la persona va a fallar.',
    sections: [
      { title: 'Tres Áreas de Liberación', content: 'El problema es que los demonios se esconden en tres lugares: en la vida de la persona, en su casa, y en la tierra/territorio de donde viene. Si solo liberas la persona pero no la casa ni la tierra, más temprano que tarde te va a fallar.' },
      { title: 'Liberación de la Persona', content: 'Identificar qué pecados trae, qué ataduras, qué líneas de iniquidad heredó. La persona llena un cuestionario confesando áreas de pecado. Luego renuncia y declara libertad sobre cada área.' },
      { title: 'Liberación de la Casa', content: 'Si liberas a la persona y no vas a su casa a sacar los demonios, va a fallar. Hay que ir físicamente a la casa, orar, echar fuera espíritus, romper objetos de brujería, limpiar espiritualmente el hogar.' },
      { title: 'Liberación de la Tierra', content: 'Cada territorio trae maldiciones específicas. Los africanos traen unas, los latinoamericanos otras, los haitianos otras. Hay que romper las maldiciones territoriales que vienen con la persona por su linaje y tierra natal.' },
      { title: 'Renuncias y Declaraciones', content: 'La persona renuncia verbalmente a cada área de atadura. Declara en voz alta su libertad. Escribe en papel las cosas que renuncia y las quema simbólicamente. Es un acto profético de liberación total.' },
    ]
  },
  6: {
    title: 'Bendición (LBS 2)',
    subtitle: 'Llenando la Casa Vacía',
    color: 'from-yellow-500 to-amber-600',
    solidColor: 'bg-yellow-500',
    tag: 'LBS 2',
    intro: 'Cuando el espíritu inmundo sale, la casa queda barrida y adornada, pero vacía. Si no llenas esa casa, regresan 7 espíritus peores. Esta semana es para llenar con el Espíritu Santo.',
    sections: [
      { title: 'El Peligro de la Casa Vacía', content: 'La Biblia dice que cuando el demonio sale, regresa y encuentra la casa limpia pero vacía. Entonces trae 7 espíritus peores y el estado final es peor que el primero. Por eso después de liberar, hay que llenar.' },
      { title: 'Cuatro Áreas a Llenar', content: 'El demonio se aloja en 4 áreas: corazón, alma, mente y cuerpo. Las cuatro deben ser llenas. Si llenas solo la mente pero no el corazón, la persona honra a Dios de labios pero su corazón está lejos.' },
      { title: 'Llenar el Corazón', content: 'El corazón se llena con fe y con la Palabra. Memorizar versículos, confesar promesas, llenar el corazón de convicción y pasión por Dios. El corazón es donde habita la fe.' },
      { title: 'Reformar el Alma', content: 'El alma (voluntad, emociones, mente) se reforma con enseñanza constante. Es un trabajo más lento pero esencial. Cambiar la manera de pensar, de sentir, de decidir.' },
      { title: 'Transformar el Cuerpo', content: 'El cuerpo debe cambiar sus hábitos. Dejar vicios, cambiar costumbres, adoptar un estilo de vida que refleje la transformación interna. El cuerpo también es templo del Espíritu.' },
      { title: 'Llenura del Espíritu Santo', content: 'El objetivo final es que la persona sea llena del Espíritu Santo. No solo salvación, sino llenura. Que hable en lenguas, que profetice, que sea un vaso lleno del poder de Dios.' },
    ]
  },
  7: {
    title: 'Sanidad (LBS 3)',
    subtitle: 'Curando el Corazón del Dolor',
    color: 'from-pink-500 to-rose-600',
    solidColor: 'bg-pink-500',
    tag: 'LBS 3',
    intro: 'Hay enfermedades espirituales que si no se curan, abren la puerta para que regresen los 7 espíritus peores. Esta semana es para sanar el corazón del dolor, la amargura, el afán y la falta de perdón.',
    sections: [
      { title: 'Enfermedades Espirituales', content: 'No todo es demonio. Hay enfermedades del alma: afán, ansiedad, amargura, falta de perdón, dolor no sanado. Estas enfermedades son puertas abiertas para que el enemigo regrese.' },
      { title: 'Sanar el Afán y la Ansiedad', content: 'El afán y la ansiedad son ladrones del alma. Roban la paz, la fe, el descanso. Hay que enseñar a echar toda ansiedad sobre Dios, a descansar en sus promesas, a vivir sin afán.' },
      { title: 'Sanar la Amargura', content: 'La amargura es una raíz que contamina a muchos. Es veneno que se guarda en el corazón y destruye desde adentro. Hay que arrancar la raíz de amargura mediante el perdón y la sanidad interior.' },
      { title: 'Sanar la Falta de Perdón', content: 'El que no perdona queda entregado a los verdugos. El perdón no es opcional, es mandato. Esta semana se trabaja el perdón profundo: perdonar al que abusó, al que traicionó, al que hirió. Perdonar para ser libre.' },
      { title: 'Curar el Corazón del Dolor', content: 'El dolor guardado en el corazón es la principal causa de recaída. Hay que ministrar sanidad interior, cerrar heridas del pasado, sanar memorias dolorosas. Un corazón sano no recae fácilmente.' },
      { title: 'Prevenir la Recaída', content: 'Cuando sanas el corazón, previenes que los 7 espíritus peores regresen. Una persona con el corazón sano, lleno del Espíritu y libre de amargura, es una fortaleza contra el enemigo.' },
      { title: 'Preparar para el Retiro', content: 'Al final de esta semana se anuncia el Retiro Final. Se dice: "La próxima semana tenemos el retiro de cierre. Viernes noche y sábado completo. Va a ser el encuentro más poderoso de tu vida."' },
    ]
  },
};

export default function SemanaPage() {
  const { weekNum, personId } = useParams();
  const navigate = useNavigate();
  const { API, getAuthHeaders, user } = useAuth();
  const [checklist, setChecklist] = useState(null);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [person, setPerson] = useState(null);

  const num = parseInt(weekNum);
  const weekData = WEEK_CONTENT[num];
  const WeekIcon = WEEK_ICONS[num] || Star;

  // Determine if we're in "person mode" or "general mode"
  const isPersonMode = !!personId;
  // Determine if current user is viewing their OWN week (persona role viewing /mi-semana)
  const isPersonSelfView = user?.rol === 'discipulo' && !personId;

  const fetchData = useCallback(async () => {
    try {
      if (isPersonMode) {
        // Fetch person data
        const personRes = await axios.get(`${API}/api/people/${personId}`, getAuthHeaders());
        setPerson(personRes.data);

        // Fetch person's checklist
        const clRes = await axios.get(`${API}/api/people/${personId}/checklists?semana=${num}`, getAuthHeaders());
        const weekChecklist = clRes.data.find(c => c.semana === num);
        setChecklist(weekChecklist);

        // Fetch person's progress
        const prRes = await axios.get(`${API}/api/people/${personId}/progress?semana=${num}`, getAuthHeaders());
        const weekProgress = prRes.data.find(p => p.semana === num);
        setProgress(weekProgress);
      } else {
        // General mode - fetch leader's own checklist and progress
        const [clRes, pRes] = await Promise.all([
          axios.get(`${API}/api/checklists`, getAuthHeaders()),
          axios.get(`${API}/api/progress`, getAuthHeaders()),
        ]);
        const weekCl = clRes.data.find(c => c.semana === num);
        const weekPr = pRes.data.find(p => p.semana === num);
        setChecklist(weekCl);
        setProgress(weekPr);
      }
    } catch (err) {
      console.error(err);
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  }, [API, getAuthHeaders, num, personId, isPersonMode]);

  useEffect(() => {
    setLoading(true);
    fetchData();
  }, [fetchData]);

  const handleCheckToggle = async (tareaId, currentValue) => {
    try {
      if (isPersonMode) {
        await axios.put(`${API}/api/people/${personId}/progress`, {
          semana: num,
          tarea_id: tareaId,
          completada: !currentValue
        }, getAuthHeaders());
      } else {
        await axios.put(`${API}/api/checklists`, {
          semana: num,
          tarea_id: tareaId,
          completada: !currentValue
        }, getAuthHeaders());
      }
      toast.success(!currentValue ? '¡Tarea completada!' : 'Tarea desmarcada');
      fetchData();
    } catch (err) {
      toast.error('Error al actualizar tarea');
    }
  };

  const handleProgressSave = async () => {
    try {
      if (isPersonMode) {
        await axios.put(`${API}/api/people/${personId}/progress`, {
          semana: num,
          casas_visitadas: progress?.casas_visitadas || 0,
          personas_contactadas: progress?.personas_contactadas || 0,
          personas_ganadas: progress?.personas_ganadas || 0,
          oraciones_realizadas: progress?.oraciones_realizadas || 0,
        }, getAuthHeaders());
      } else {
        await axios.put(`${API}/api/progress`, {
          semana: num,
          casas_visitadas: progress?.casas_visitadas || 0,
          personas_contactadas: progress?.personas_contactadas || 0,
          personas_ganadas: progress?.personas_ganadas || 0,
          oraciones_realizadas: progress?.oraciones_realizadas || 0,
        }, getAuthHeaders());
      }
      toast.success('Progreso guardado exitosamente');
    } catch (err) {
      toast.error('Error al guardar progreso');
    }
  };

  if (!weekData) return <div className="p-8 text-center"><p>Semana no encontrada</p></div>;

  const completedTasks = checklist?.tareas?.filter(t => t.completada).length || 0;
  const totalTasks = checklist?.tareas?.length || 0;
  const progressPct = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  const navigatePrev = () => {
    if (isPersonMode) {
      if (num > 1) navigate(`/persona/${personId}/semana/${num - 1}`);
      else navigate('/registro');
    } else {
      if (num > 1) navigate(`/semana/${num - 1}`);
      else navigate('/mapa');
    }
  };

  const navigateNext = () => {
    if (isPersonMode) {
      if (num < 7) navigate(`/persona/${personId}/semana/${num + 1}`);
    } else {
      if (num < 7) navigate(`/semana/${num + 1}`);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
      <div className="px-3 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-10 space-y-4 sm:space-y-6 max-w-5xl mx-auto">
        {/* Person Context Banner (if in person mode) */}
        {isPersonMode && person && (
          <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }}>
            <div className="bg-white rounded-xl shadow-sm border-2 border-[#1FA6A0] p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#1FA6A0] to-[#1B2A4A] flex items-center justify-center">
                    <UserCircle className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Administrando progreso de:</p>
                    <p className="font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>{person.nombre}</p>
                  </div>
                </div>
                <Button variant="outline" size="sm" onClick={() => navigate('/registro')}>
                  <ArrowLeft className="w-3.5 h-3.5 mr-1" />
                  Volver a Personas
                </Button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between">
          <Button variant="ghost" size="sm" onClick={navigatePrev} data-testid="week-nav-prev" className="hover:bg-white">
            <ChevronLeft className="w-4 h-4 mr-1" /> 
            {isPersonMode ? (num > 1 ? `Semana ${num - 1}` : 'Personas') : (num > 1 ? `Semana ${num - 1}` : 'Mapa')}
          </Button>
          {num < 7 && (
            <Button variant="ghost" size="sm" onClick={navigateNext} data-testid="week-nav-next" className="hover:bg-white">
              Semana {num + 1} <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          )}
        </div>

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <div className={`rounded-2xl bg-gradient-to-r ${weekData.color} p-6 sm:p-8 text-white relative overflow-hidden shadow-xl`}>
            <div className="absolute inset-0 opacity-10">
              <div className="absolute inset-0" style={{
                backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.15) 1px, transparent 0)',
                backgroundSize: '32px 32px'
              }}></div>
            </div>
            <div className="absolute top-0 right-0 w-40 h-40 bg-white/5 rounded-full -translate-y-16 translate-x-16"></div>
            <div className="absolute bottom-0 left-0 w-24 h-24 bg-white/5 rounded-full translate-y-8 -translate-x-8"></div>
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-3">
                <Badge className="bg-white/20 text-white border-0 font-semibold">{weekData.tag}</Badge>
                <span className="text-white/60 text-sm">Semana {num} de 7</span>
                {progressPct === 100 && (
                  <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring' }}>
                    <Badge className="bg-white/30 text-white border-0"><Trophy className="w-3 h-3 mr-1" /> Completada</Badge>
                  </motion.div>
                )}
              </div>
              <div className="flex items-center gap-3 mb-2">
                <motion.div animate={{ rotate: [0, 10, -10, 0] }} transition={{ duration: 3, repeat: Infinity }}>
                  <WeekIcon className="w-8 h-8 text-white/80" />
                </motion.div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold" style={{ fontFamily: 'Spectral, serif' }}>
                  Semana {num}: {weekData.title}
                </h1>
              </div>
              <p className="text-white/80 text-sm mb-1">{weekData.subtitle}</p>
              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="text-white/50 text-xs italic mt-2">
                {WEEK_MOTIVATIONS[num]}
              </motion.p>
              <div className="mt-5 flex items-center gap-3">
                <div className="flex-1 h-3 rounded-full bg-white/20 overflow-hidden">
                  <motion.div className="h-full rounded-full bg-white/80" initial={{ width: 0 }} animate={{ width: `${progressPct}%` }} transition={{ duration: 1, delay: 0.3 }} />
                </div>
                <span className="text-sm font-bold">{progressPct}%</span>
              </div>
            </div>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Content */}
          <div className="lg:col-span-2 space-y-4">
            {/* Intro */}
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.15 }}>
              <div className="bg-white rounded-xl shadow-md border border-[#E7E2D6] p-6 border-l-4 border-l-[#C8A951]">
                <div className="flex items-start gap-3">
                  <motion.div animate={{ scale: [1, 1.1, 1] }} transition={{ duration: 2, repeat: Infinity }} className="shrink-0 mt-1">
                    <Flame className="w-5 h-5 text-[#C8A951]" />
                  </motion.div>
                  <p className="reading-content text-base leading-7 text-foreground italic">{weekData.intro}</p>
                </div>
              </div>
            </motion.div>

            {/* Sections */}
            {weekData.sections.map((section, idx) => (
              <motion.div key={idx} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.2 + idx * 0.06 }} whileHover={{ x: 2 }}>
                <div className="bg-white rounded-xl shadow-md border border-[#E7E2D6] p-6 hover:shadow-lg transition-all duration-300 hover:border-[#C8A951]/40">
                  <div className="flex items-center gap-2 mb-3">
                    <div className={`w-7 h-7 rounded-lg ${weekData.solidColor} flex items-center justify-center text-white text-xs font-bold`}>{idx + 1}</div>
                    <h3 className="text-lg font-bold gradient-underline inline-block" style={{ fontFamily: 'Spectral, serif' }}>{section.title}</h3>
                  </div>
                  <p className="reading-content text-sm leading-7 text-muted-foreground pl-9">{section.content}</p>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Checklist */}
            <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4, delay: 0.25 }}>
              <div className="bg-white rounded-xl shadow-md border border-[#E7E2D6] overflow-hidden">
                <div className={`bg-gradient-to-r ${weekData.color} px-4 py-3`}>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-white" />
                    <span className="text-white font-semibold text-sm" style={{ fontFamily: 'Spectral, serif' }}>Lista de Tareas</span>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <div className="flex-1 h-1.5 rounded-full bg-white/20 overflow-hidden">
                      <motion.div className="h-full rounded-full bg-white/80" initial={{ width: 0 }} animate={{ width: `${progressPct}%` }} transition={{ duration: 0.8, delay: 0.5 }} />
                    </div>
                    <span className="text-white text-xs font-medium">{completedTasks}/{totalTasks}</span>
                  </div>
                </div>
                <div className="p-3 space-y-1">
                  {loading ? (
                    <p className="text-sm text-muted-foreground p-3">Cargando...</p>
                  ) : (
                    checklist?.tareas?.map((tarea, idx) => (
                      <motion.div key={tarea.id} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + idx * 0.04 }}
                        className={`flex items-start gap-3 p-2.5 rounded-lg transition-all duration-200 cursor-pointer ${tarea.completada ? 'bg-[#1FA6A0]/5' : 'hover:bg-[#F5F0E8]'}`}
                        onClick={() => handleCheckToggle(tarea.id, tarea.completada)}
                      >
                        <Checkbox checked={tarea.completada} onCheckedChange={() => handleCheckToggle(tarea.id, tarea.completada)} data-testid={`checklist-${tarea.id}`} />
                        <span className={`text-sm leading-relaxed transition-all duration-200 ${tarea.completada ? 'line-through text-muted-foreground/50' : 'text-foreground'}`}>{tarea.texto}</span>
                      </motion.div>
                    ))
                  )}
                </div>
              </div>
            </motion.div>

            {/* Validaciones Personales (solo cuando una PERSONA ve su propia semana).
                Los contadores globales (casas visitadas, personas contactadas, etc.)
                se trasladaron a la Bitácora Evangelística del líder — no pertenecen al
                perfil individual de cada consolidado. */}
            {isPersonSelfView && (
              <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4, delay: 0.3 }}>
                <div className="bg-white rounded-xl shadow-md border border-[#E7E2D6] overflow-hidden">
                  <div className="bg-gradient-to-r from-[#1B2A4A] to-[#2A3D63] px-4 py-3">
                    <span className="text-white font-semibold text-sm" style={{ fontFamily: 'Spectral, serif' }}>Validación Personal</span>
                  </div>
                  <div className="p-4">
                    <div className="space-y-2">
                      <Label className="text-xs font-semibold text-[#1B2A4A]">Confirma tu compromiso esta semana:</Label>
                      <div className="space-y-2 bg-[#F5F0E8] rounded-lg p-3">
                        <div className="flex items-start gap-2">
                          <Checkbox
                            checked={progress?.validacion_leyo_libro || false}
                            onCheckedChange={async (checked) => {
                              try {
                                await axios.put(`${API}/api/people/${user.id}/progress`, {
                                  semana: num,
                                  validacion_leyo_libro: checked
                                }, getAuthHeaders());
                                setProgress(prev => ({ ...prev, validacion_leyo_libro: checked }));
                                toast.success(checked ? '✓ Validado' : 'Validación removida');
                              } catch (err) {
                                toast.error('Error al actualizar');
                              }
                            }}
                            className="mt-0.5"
                          />
                          <label className="text-xs cursor-pointer">
                            Confirmo que leí el libro/material de esta semana completo
                          </label>
                        </div>
                        <div className="flex items-start gap-2">
                          <Checkbox
                            checked={progress?.validacion_hizo_oraciones || false}
                            onCheckedChange={async (checked) => {
                              try {
                                await axios.put(`${API}/api/people/${user.id}/progress`, {
                                  semana: num,
                                  validacion_hizo_oraciones: checked
                                }, getAuthHeaders());
                                setProgress(prev => ({ ...prev, validacion_hizo_oraciones: checked }));
                                toast.success(checked ? '✓ Validado' : 'Validación removida');
                              } catch (err) {
                                toast.error('Error al actualizar');
                              }
                            }}
                            className="mt-0.5"
                          />
                          <label className="text-xs cursor-pointer">
                            Confirmo que hice todas las oraciones indicadas
                          </label>
                        </div>
                        <div className="flex items-start gap-2">
                          <Checkbox
                            checked={progress?.validacion_visito_casas || false}
                            onCheckedChange={async (checked) => {
                              try {
                                await axios.put(`${API}/api/people/${user.id}/progress`, {
                                  semana: num,
                                  validacion_visito_casas: checked
                                }, getAuthHeaders());
                                setProgress(prev => ({ ...prev, validacion_visito_casas: checked }));
                                toast.success(checked ? '✓ Validado' : 'Validación removida');
                              } catch (err) {
                                toast.error('Error al actualizar');
                              }
                            }}
                            className="mt-0.5"
                          />
                          <label className="text-xs cursor-pointer">
                            Confirmo que visité las casas y cumplí con las actividades
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Atajo a la Bitácora (solo líderes/pastores viendo la semana de una persona) */}
            {!isPersonSelfView && (
              <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4, delay: 0.3 }}>
                <div className="relative overflow-hidden bg-gradient-to-br from-[#0F1A33] via-[#1B2A4A] to-[#2A3D63] rounded-xl shadow-md text-white p-4">
                  <div className="absolute -top-10 -right-10 w-32 h-32 bg-[#C8A951]/10 rounded-full blur-2xl pointer-events-none" />
                  <div className="relative z-10">
                    <p className="text-[10px] uppercase tracking-[0.25em] text-[#C8A951] font-bold">Registro Ministerial</p>
                    <h4 className="text-base font-bold mt-1" style={{ fontFamily: 'Spectral, serif' }}>
                      Tu jornada <span className="text-[#C8A951] italic">se anota aparte</span>
                    </h4>
                    <p className="text-xs text-white/70 leading-relaxed mt-2">
                      Las casas visitadas, personas contactadas y oraciones del día pertenecen a
                      tu <strong className="text-[#C8A951]">Bitácora Evangelística</strong>, no al perfil individual.
                    </p>
                    <button
                      onClick={() => navigate('/bitacora')}
                      className="mt-3 w-full text-xs font-bold bg-[#C8A951] text-[#0F1A33] rounded-lg py-2 hover:bg-[#E2CF8A] transition-colors"
                      data-testid="btn-ir-bitacora"
                    >
                      Ir a la Bitácora →
                    </button>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Motivational Card */}
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }} whileHover={{ scale: 1.02 }}>
              <div className="bg-gradient-to-br from-[#1B2A4A] to-[#2A3D63] rounded-xl p-4 text-white relative overflow-hidden shadow-lg">
                <div className="absolute inset-0 opacity-10">
                  <div className="absolute inset-0" style={{
                    backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.15) 1px, transparent 0)',
                    backgroundSize: '24px 24px'
                  }}></div>
                </div>
                <div className="relative z-10">
                  <motion.div animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 2, repeat: Infinity }}>
                    <Flame className="w-5 h-5 text-[#C8A951] mb-2" />
                  </motion.div>
                  <p className="text-white/80 text-xs italic leading-relaxed">{WEEK_MOTIVATIONS[num]}</p>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
}
