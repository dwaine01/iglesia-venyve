import React from 'react';
import { BriefcaseBusiness, Church, Sparkles, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import PersonCanonicalLink from '../PersonCanonicalLink';
import { Badge } from '../ui/badge';
import { Card, CardContent } from '../ui/card';

const genderLabel = (value) => ({
  masculino: 'Masculino',
  femenino: 'Femenino',
  no_especificado: 'No especificado',
}[value] || value);

export const DirectoryPersonCard = ({ person }) => {
  const initials = person.nombre_completo
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join('');

  return (
    <Card
      className="group overflow-hidden rounded-lg border-slate-200 shadow-sm transition-[transform,box-shadow,border-color] duration-200 hover:-translate-y-1 hover:border-amber-300 hover:shadow-lg"
      data-testid={`person-card-${person.person_id}`}
    >
      <CardContent className="p-0">
        <PersonCanonicalLink
          personId={person.person_id}
          testId={`person-canonical-link-${person.person_id}`}
          className="block p-5 hover:no-underline"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-slate-900 font-semibold text-amber-300">
              {initials || <UserRound className="h-5 w-5" />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-lg font-semibold text-slate-950" data-testid={`person-name-${person.person_id}`}>
                {person.nombre_completo}
              </p>
              <p className="font-mono text-xs text-amber-700" data-testid={`person-number-${person.person_id}`}>
                {person.person_number || 'VV pendiente'}
              </p>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                {person.age_group_label && <span>{person.age_years} años · {person.age_group_label}</span>}
                {person.genero && <span>{genderLabel(person.genero)}</span>}
              </div>
            </div>
          </div>
        </PersonCanonicalLink>

        <div className="space-y-4 border-t border-slate-100 px-5 py-4">
          <div>
            <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
              <BriefcaseBusiness className="h-4 w-4" />Ocupación
            </p>
            <p className="text-sm font-medium text-slate-800">
              {person.talents?.ocupacion_principal?.nombre || 'No registrada'}
            </p>
          </div>

          {person.talents?.habilidades?.length > 0 && (
            <div>
              <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
                <Sparkles className="h-4 w-4" />Habilidades
              </p>
              <div className="flex flex-wrap gap-1.5">
                {person.talents.habilidades.slice(0, 4).map((skill) => (
                  <Badge key={skill.talent_id} variant="secondary">{skill.nombre}</Badge>
                ))}
              </div>
            </div>
          )}

          {person.ministries?.length > 0 && (
            <div>
              <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
                <Church className="h-4 w-4" />Ministerios
              </p>
              <div className="flex flex-wrap gap-1.5">
                {person.ministries.slice(0, 3).map((assignment) => (
                  <Link
                    key={assignment.assignment_id}
                    to={assignment.ministry_path}
                    onClick={(event) => event.stopPropagation()}
                    data-testid={`person-ministry-link-${assignment.assignment_id}`}
                    className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-900 transition-colors hover:bg-amber-100"
                  >
                    {assignment.ministry_name} · {assignment.role_name}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};