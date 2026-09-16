import {
  displayLabel,
  meetingModalityLabel,
  minuteTypeLabel,
  priorityLabel,
  processLabel,
  processStageLabel,
  roleLabel,
  speakerLabel,
  stageLabel,
  statusLabel,
  translateTechnicalText,
} from './displayLabels';

describe.each([
  ['ready_for_cellular', 'Listo para integrarse a una célula'],
  ['new_visitor', 'Nuevo visitante'],
  ['seven_weeks', '7 Semanas'],
  ['in_progress', 'En proceso'],
  ['due_soon', 'Próximo a vencer'],
  ['on_sla', 'Seguimiento a tiempo'],
  ['follow_up_required', 'Requiere seguimiento'],
  ['ai_draft', 'Borrador asistido por IA'],
  ['speaker_0', 'Participante 1'],
  ['door_6', 'Puerta 6'],
  ['recien_iniciado', 'Recién iniciado'],
  ['meta_baja', 'Requiere acompañamiento'],
])('etiquetas pastorales', (internalValue, expectedLabel) => {
  test(`${internalValue} se presenta como ${expectedLabel}`, () => {
    expect(displayLabel(internalValue)).toBe(expectedLabel);
  });
});

test('las funciones especializadas conservan la capa pastoral', () => {
  expect(statusLabel('completed')).toBe('Completado');
  expect(processLabel('cap')).toBe('Encuentra tu lugar para servir');
  expect(stageLabel('week_4')).toBe('Semana 4');
  expect(roleLabel('cell_leader')).toBe('Líder de célula');
  expect(priorityLabel('urgent')).toBe('Urgente');
  expect(meetingModalityLabel('hybrid')).toBe('Híbrida');
  expect(minuteTypeLabel('human_draft')).toBe('Borrador humano');
  expect(minuteTypeLabel('manual')).toBe('Minuta manual');
  expect(speakerLabel('speaker_2')).toBe('Participante 3');
});

test('una etapa compuesta no expone claves internas', () => {
  expect(processStageLabel('seven_weeks:week_3')).toBe('7 Semanas · Semana 3');
});

test('el texto técnico dentro de una oración se traduce', () => {
  expect(translateTechnicalText('SLA del Pipeline para ready_for_cellular')).toBe(
    'tiempo de seguimiento del recorrido de acompañamiento para Listo para integrarse a una célula'
  );
});

test('los errores estructurados se convierten en mensajes legibles', () => {
  expect(translateTechnicalText([{ msg: 'ready_for_cellular' }, { message: 'SLA vencido' }])).toBe(
    'Listo para integrarse a una célula · tiempo de seguimiento vencido'
  );
});

test('los módulos pueden usar un texto seguro para valores desconocidos', () => {
  expect(displayLabel('future_internal_code', 'Estado por confirmar')).toBe('Estado por confirmar');
  expect(statusLabel('future_internal_code')).toBe('Sin estado');
});