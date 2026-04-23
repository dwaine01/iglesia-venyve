import React from 'react';
import { Badge } from './ui/badge';
import { Rocket, CheckCircle2, Trophy, AlertCircle, Users } from 'lucide-react';

/**
 * StatusBadge - Renderiza un badge dinámico basado en el estado calculado por el backend.
 * Estados soportados:
 *  - excelente    → dorado (Meta alcanzada o adelantado)
 *  - bien         → turquesa (En ritmo)
 *  - recien_iniciado → azul (Dentro de los 7 días de gracia)
 *  - meta_baja    → naranja/rojo (Atrasado)
 *  - sin_personas → gris (Líder sin personas asignadas)
 */
export const StatusBadge = ({ status, showPct = false, size = 'default' }) => {
  if (!status) return null;

  const config = {
    excelente: {
      bg: 'bg-gradient-to-r from-[#C8A951] to-[#E2CF8A]',
      text: 'text-[#1B2A4A]',
      border: 'border-[#C8A951]',
      Icon: Trophy,
    },
    bien: {
      bg: 'bg-gradient-to-r from-[#1FA6A0] to-[#3BC0B8]',
      text: 'text-white',
      border: 'border-[#1FA6A0]',
      Icon: CheckCircle2,
    },
    recien_iniciado: {
      bg: 'bg-gradient-to-r from-blue-500 to-blue-600',
      text: 'text-white',
      border: 'border-blue-500',
      Icon: Rocket,
    },
    meta_baja: {
      bg: 'bg-gradient-to-r from-orange-500 to-red-500',
      text: 'text-white',
      border: 'border-orange-500',
      Icon: AlertCircle,
    },
    sin_personas: {
      bg: 'bg-gray-400',
      text: 'text-white',
      border: 'border-gray-400',
      Icon: Users,
    },
  };

  const cfg = config[status.key] || config.bien;
  const { Icon } = cfg;

  const sizeClasses = size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs';

  return (
    <Badge
      data-testid={`status-badge-${status.key}`}
      className={`${cfg.bg} ${cfg.text} ${sizeClasses} font-semibold border-0 shadow-sm inline-flex items-center gap-1`}
    >
      <Icon className={size === 'lg' ? 'w-4 h-4' : 'w-3 h-3'} />
      {status.label}
      {showPct && status.actual_pct !== undefined && (
        <span className="ml-1 opacity-90">({status.actual_pct}%)</span>
      )}
    </Badge>
  );
};

/**
 * ProgressVsExpected - Barra visual que compara el progreso actual vs el esperado según el tiempo.
 */
export const ProgressVsExpected = ({ status, compact = false, inverted = false }) => {
  if (!status) return null;
  const { actual_pct = 0, expected_pct = 0, days_elapsed = 0, gap = 0 } = status;

  const gapLabel =
    gap >= 10
      ? `+${gap.toFixed(0)}% adelantado`
      : gap <= -10
      ? `${gap.toFixed(0)}% atrasado`
      : 'En ritmo';

  const gapColor = gap >= 10 ? 'text-[#C8A951]' : gap <= -10 ? 'text-orange-400' : 'text-[#1FA6A0]';
  const labelText = inverted ? 'text-white/70' : 'text-muted-foreground';
  const valueText = inverted ? 'text-white' : 'text-[#1B2A4A]';
  const trackBg = inverted ? 'bg-white/15' : 'bg-[#E7E2D6]';
  const markerBg = inverted ? 'bg-[#C8A951]' : 'bg-[#1B2A4A]';
  const footerText = inverted ? 'text-white/60' : 'text-muted-foreground';

  return (
    <div className={compact ? 'space-y-1' : 'space-y-2'} data-testid="progress-vs-expected">
      <div className="flex items-center justify-between text-xs">
        <span className={labelText}>Real: <span className={`font-bold ${valueText}`}>{actual_pct.toFixed(0)}%</span></span>
        <span className={labelText}>Esperado: <span className={`font-bold ${valueText}`}>{expected_pct.toFixed(0)}%</span></span>
      </div>
      <div className={`relative h-2 ${trackBg} rounded-full overflow-hidden`}>
        {/* Línea del esperado */}
        <div
          className={`absolute top-0 bottom-0 w-0.5 ${markerBg} z-10`}
          style={{ left: `${Math.min(100, expected_pct)}%` }}
          title={`Esperado: ${expected_pct.toFixed(0)}%`}
        />
        {/* Barra real */}
        <div
          className="h-full bg-gradient-to-r from-[#1FA6A0] via-[#C8A951] to-[#E2CF8A] transition-all"
          style={{ width: `${Math.min(100, actual_pct)}%` }}
        />
      </div>
      {!compact && (
        <div className="flex items-center justify-between text-[10px]">
          <span className={footerText}>Día {days_elapsed} de 49</span>
          <span className={`font-bold ${gapColor}`}>{gapLabel}</span>
        </div>
      )}
    </div>
  );
};

export default StatusBadge;
