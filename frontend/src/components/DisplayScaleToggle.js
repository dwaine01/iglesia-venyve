import React from 'react';
import { Button } from './ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { Maximize2, Tv, Monitor, Check, Laptop } from 'lucide-react';
import { useDisplayScale, SCALE_LEVELS } from '../hooks/useDisplayScale';

const ICONS_BY_VALUE = {
  1.0: Laptop,
  1.35: Monitor,
  1.7: Tv,
};

/**
 * Toggle visible en el header del panel para que la pastora pueda escalar
 * todo el contenido cuando el panel se proyecta en la pantalla LED del
 * auditorio (17x7 pies). NO altera la estructura: solo aumenta el tamano
 * proporcional de TODOS los elementos.
 */
export default function DisplayScaleToggle() {
  const { scale, setScale } = useDisplayScale();

  const current = SCALE_LEVELS.find((l) => l.value === scale) || SCALE_LEVELS[0];
  const isExpanded = scale > 1;
  const CurrentIcon = ICONS_BY_VALUE[scale] || Laptop;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant={isExpanded ? 'default' : 'ghost'}
          size="sm"
          className={
            isExpanded
              ? 'gap-1.5 bg-[#1B2A4A] hover:bg-[#0F1A33] text-white shadow-sm'
              : 'gap-1.5 text-muted-foreground hover:text-foreground'
          }
          data-testid="display-scale-toggle"
          aria-label={`Tamano actual: ${current.label}. Cambiar tamano de pantalla`}
          title="Cambiar tamano de pantalla (proyeccion en auditorio)"
        >
          <CurrentIcon className="w-4 h-4 shrink-0" />
          <span className="hidden sm:inline text-xs font-semibold">
            {isExpanded ? current.label : 'Tamano'}
          </span>
          {isExpanded && (
            <span className="hidden md:inline text-[10px] font-mono opacity-80">
              {current.shortLabel}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-64" data-testid="display-scale-menu">
        <DropdownMenuLabel className="flex items-center gap-2">
          <Maximize2 className="w-4 h-4 text-[#C8A951]" />
          <span>Tamano del panel</span>
        </DropdownMenuLabel>
        <p className="px-2 pb-2 text-[11px] text-muted-foreground leading-snug">
          Escala todo proporcionalmente. Util cuando el panel se proyecta en una
          pantalla grande del auditorio.
        </p>
        <DropdownMenuSeparator />

        {SCALE_LEVELS.map((level) => {
          const Icon = ICONS_BY_VALUE[level.value] || Laptop;
          const active = level.value === scale;
          return (
            <DropdownMenuItem
              key={level.value}
              onSelect={(e) => {
                e.preventDefault();
                setScale(level.value);
              }}
              className={`gap-3 cursor-pointer py-2.5 ${
                active ? 'bg-[#F5F0E8] text-[#1B2A4A] font-medium' : ''
              }`}
              data-testid={`display-scale-option-${level.value}`}
            >
              <Icon className={`w-5 h-5 shrink-0 ${active ? 'text-[#C8A951]' : 'text-muted-foreground'}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{level.label}</span>
                  <span className="text-[10px] font-mono text-muted-foreground">
                    {level.shortLabel}
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-tight">
                  {level.description}
                </p>
              </div>
              {active && <Check className="w-4 h-4 text-[#C8A951] shrink-0" />}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export { DisplayScaleToggle };
