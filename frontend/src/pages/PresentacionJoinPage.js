import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { MonitorPlay, ArrowRight, Home } from 'lucide-react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

export default function PresentacionJoinPage() {
  const navigate = useNavigate();
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  const join = async () => {
    const c = code.trim();
    if (c.length !== 4) { toast.error('El código debe ser de 4 dígitos'); return; }
    setLoading(true);
    try {
      await axios.get(`${API}/api/presentation/session/${c}`);
      navigate(`/presentacion/audiencia/${c}`);
    } catch (err) {
      toast.error('Sesión no encontrada o ya terminó');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0F1A33] via-[#1B2A4A] to-purple-900 flex items-center justify-center px-4 py-10">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md">
        <Card className="shadow-2xl border-0 bg-white/5 backdrop-blur-xl border border-white/10">
          <CardContent className="p-6 sm:p-8 text-white">
            <div className="text-center mb-6">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] flex items-center justify-center mx-auto mb-4 shadow-xl">
                <MonitorPlay className="w-8 h-8 text-[#1B2A4A]" />
              </div>
              <h1 className="text-2xl font-bold mb-1" style={{ fontFamily: 'Spectral, serif' }}>Unirse a Presentación</h1>
              <p className="text-sm text-white/60">Ingresa el código de 4 dígitos del presentador</p>
            </div>

            <div className="space-y-4">
              <div>
                <Label htmlFor="code" className="text-white/80 text-xs uppercase tracking-widest">Código de Sesión</Label>
                <Input
                  id="code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 4))}
                  onKeyDown={(e) => e.key === 'Enter' && join()}
                  maxLength={4}
                  placeholder="0000"
                  className="text-center text-4xl sm:text-5xl font-mono tracking-[0.6em] font-bold bg-white/10 border-[#C8A951]/40 text-[#C8A951] h-16 sm:h-20 mt-2 placeholder:text-white/20"
                  data-testid="input-codigo-sesion"
                  autoFocus
                />
              </div>

              <Button onClick={join} disabled={loading || code.length !== 4}
                className="w-full bg-[#C8A951] hover:bg-[#E2CF8A] text-[#1B2A4A] font-bold h-12 text-base gap-2"
                data-testid="btn-unirse">
                {loading ? 'Conectando...' : 'Unirse a la Presentación'}
                {!loading && <ArrowRight className="w-5 h-5" />}
              </Button>

              <Button variant="ghost" onClick={() => navigate('/presentacion')}
                className="w-full text-white/60 hover:text-white hover:bg-white/10 gap-1.5">
                <Home className="w-4 h-4" /> Volver
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
