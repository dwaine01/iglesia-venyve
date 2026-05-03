import React from 'react';
import { Crown, Shield, Users, Hammer, Sprout } from 'lucide-react';

const CONFIG = {
  maestro:    { label: 'Maestro',         icon: Crown,  color: 'from-[#C8A951] to-[#E2CF8A]', text: 'text-[#1B2A4A]', ring: 'ring-[#C8A951]' },
  supervisor: { label: 'Supervisor',      icon: Shield, color: 'bg-[#1FA6A0]',                text: 'text-white',     ring: 'ring-[#1FA6A0]' },
  lider:      { label: 'Líder de Grupo', icon: Users,  color: 'bg-[#1B2A4A]',            text: 'text-white',     ring: 'ring-[#1B2A4A]' },
  obrero:     { label: 'Obrero',          icon: Hammer, color: 'bg-[#2A3D63]',                text: 'text-white',     ring: 'ring-[#2A3D63]' },
  discipulo:  { label: 'Discípulo',  icon: Sprout, color: 'bg-emerald-700',              text: 'text-white',     ring: 'ring-emerald-700' },
};

export function RoleBadge({ rol, size = 'md', className = '' }) {
  const c = CONFIG[rol] || CONFIG.discipulo;
  const Icon = c.icon;
  const sizeCls = size === 'sm'
    ? 'text-[10px] px-2 py-0.5 gap-1'
    : size === 'lg'
    ? 'text-sm px-3 py-1.5 gap-2'
    : 'text-xs px-2.5 py-1 gap-1.5';
  const iconSize = size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5';
  const bgClass = c.color.startsWith('from-') ? `bg-gradient-to-r ${c.color}` : c.color;
  return (
    <span
      data-testid={`role-badge-${rol}`}
      className={`inline-flex items-center font-bold uppercase tracking-wider rounded-full ${bgClass} ${c.text} ${sizeCls} ${className}`}
    >
      <Icon className={iconSize} />
      {c.label}
    </span>
  );
}

export default RoleBadge;
