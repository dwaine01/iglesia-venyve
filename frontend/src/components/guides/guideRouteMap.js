const exact = {
  '/dashboard-general': 'dashboard_general',
  '/nucleo': 'core_governance',
  '/procesos/dashboard': 'processes_dashboard',
  '/procesos/7-semanas': 'processes_seven_weeks',
  '/procesos/consolidacion': 'processes_consolidation',
  '/procesos/mentoria': 'processes_mentorship',
  '/procesos/cap': 'processes_cap',
  '/personas': 'persons_directory',
  '/personas/nueva': 'person_create',
  '/directorio': 'talent_directory',
  '/ministerios': 'ministries',
  '/bitacora': 'evangelism_journal',
  '/codigos': 'invite_codes',
  '/estadisticas': 'statistics',
  '/presentacion': 'seven_weeks_manual',
  '/introduccion': 'seven_weeks_manual',
  '/mapa': 'seven_weeks_manual',
  '/mi-progreso': 'personal_progress',
};

export const resolveRouteGuide = (pathname, role) => {
  if (pathname === '/' || pathname === '/dashboard') {
    if (role === 'persona') return 'personal_progress';
    if (role === 'lider') return 'leader_dashboard';
    return 'processes_dashboard';
  }
  if (exact[pathname]) return exact[pathname];
  if (/^\/procesos\/7-semanas\/[^/]+$/.test(pathname)) return 'processes_seven_weeks_detail';
  if (/^\/personas\/[^/]+$/.test(pathname)) return 'person_profile';
  if (/^\/ministerios\/[^/]+$/.test(pathname)) return 'ministry_detail';
  if (/^\/lider\/[^/]+\/dashboard$/.test(pathname)) return 'leader_dashboard';
  return null;
};