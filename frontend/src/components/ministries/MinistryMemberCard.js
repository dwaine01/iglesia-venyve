import React from 'react';
import { CalendarDays, UserMinus } from 'lucide-react';
import PersonCanonicalLink from '../PersonCanonicalLink';
import PersonPhoto from '../PersonPhoto';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';

export const MinistryMemberCard = ({ member, onDeactivate }) => (
  <Card className="rounded-lg border-slate-200 shadow-sm" data-testid={`ministry-member-row-${member.person_id}`}>
    <CardContent className="flex gap-3 p-4">
      <PersonPhoto personId={member.person_id} available={member.photo_available} name={member.nombre_completo} />
      <div className="min-w-0 flex-1">
        <PersonCanonicalLink personId={member.person_id} testId={`ministry-member-profile-link-${member.person_id}`} className="font-semibold text-slate-950">
          {member.nombre_completo}
        </PersonCanonicalLink>
        <p className="font-mono text-xs text-amber-700">{member.person_number}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Badge variant="outline">{member.role_name}</Badge>
          {member.fecha_inicio && <span className="flex items-center gap-1 text-xs text-slate-500"><CalendarDays className="h-3.5 w-3.5" />Desde {member.fecha_inicio}</span>}
        </div>
      </div>
      <Button
        variant="ghost"
        size="icon"
        aria-label={`Retirar a ${member.nombre_completo}`}
        data-testid={`ministry-deactivate-assignment-${member.assignment_id}`}
        onClick={() => onDeactivate(member)}
        className="shrink-0 text-slate-400 hover:text-red-700"
      >
        <UserMinus className="h-4 w-4" />
      </Button>
    </CardContent>
  </Card>
);