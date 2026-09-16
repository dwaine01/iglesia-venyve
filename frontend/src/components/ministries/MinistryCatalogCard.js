import React from 'react';
import { Archive, Church, UsersRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';

export const MinistryCatalogCard = ({ ministry, onArchive }) => (
  <Card
    className="overflow-hidden rounded-lg border-slate-200 shadow-sm transition-[transform,box-shadow,border-color] duration-200 hover:-translate-y-1 hover:border-amber-300 hover:shadow-lg"
    data-testid={`ministry-card-${ministry.ministry_id}`}
  >
    <CardContent className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-amber-100 text-amber-800">
          <Church className="h-5 w-5" />
        </div>
        <Badge
          variant="outline"
          className={ministry.leadership_vacancy ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}
          data-testid={`ministry-leadership-status-${ministry.ministry_id}`}
        >
          {ministry.leadership_vacancy ? 'Liderazgo vacante' : 'Liderazgo activo'}
        </Badge>
      </div>
      <Link
        to={ministry.canonical_ministry_path}
        data-testid={`ministry-detail-link-${ministry.ministry_id}`}
        className="mt-5 block text-xl font-bold text-slate-950 transition-colors hover:text-amber-800"
      >
        {ministry.nombre}
      </Link>
      <p className="mt-2 min-h-10 text-sm leading-5 text-slate-500">
        {ministry.descripcion || 'Unidad ministerial activa'}
      </p>
      <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4">
        <span className="flex items-center gap-2 text-sm text-slate-600" data-testid={`ministry-people-count-${ministry.ministry_id}`}>
          <UsersRound className="h-4 w-4" />{ministry.active_people_count} personas
        </span>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Archivar ${ministry.nombre}`}
          data-testid={`ministry-archive-button-${ministry.ministry_id}`}
          onClick={() => onArchive(ministry)}
          className="text-slate-400 hover:text-red-700"
        >
          <Archive className="h-4 w-4" />
        </Button>
      </div>
    </CardContent>
  </Card>
);