import React from 'react';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

// Gráficas del Reporte de invasión (recharts, la misma librería de Mi Grupo
// Frontal). Reglas: valores y etiquetas siempre visibles (no solo color),
// estados vacíos claros y legibles en celular (ancho completo).
export const COLORS = {
  navy: '#1e3a5f', blue: '#2563eb', green: '#15803d', amber: '#b45309', red: '#b91c1c', slate: '#64748b', violet: '#6d28d9', teal: '#0f766e', gold: '#8a6d1f',
};
export const PALETTE = [COLORS.blue, COLORS.green, COLORS.amber, COLORS.violet, COLORS.teal, COLORS.red, COLORS.slate, COLORS.gold];
const AXIS = { fontSize: 11, fill: '#475569' };

export const Empty = ({ text = 'Aún sin datos' }) => <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500" data-testid="chart-empty">{text}</div>;
const hasValues = (data, keys) => data?.length && data.some((row) => keys.some((key) => Number(row[key]) > 0));

export function ChartCard({ title, subtitle, children, testId }) {
  return (
    <figure className="print-break-avoid min-w-0 rounded-xl border border-[#EEECE6] bg-white p-3" data-testid={testId}>
      <figcaption className="mb-2"><p className="text-sm font-semibold text-[#101D36]">{title}</p>{subtitle && <p className="text-[11px] text-slate-500">{subtitle}</p>}</figcaption>
      {children}
    </figure>
  );
}

// Barras horizontales con el valor al final (rankings, embudo, sectores).
export function HBars({ data, valueKey = 'value', nameKey = 'name', color = COLORS.blue, colors, format = (value) => value, height, max, labelKey }) {
  if (!hasValues(data, [valueKey])) return <Empty />;
  const chartHeight = height || Math.max(140, data.length * 34 + 30);
  return (
    <div style={{ height: chartHeight }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 4, right: 48, top: 4, bottom: 4 }}>
          <CartesianGrid horizontal={false} stroke="#EEECE6" />
          <XAxis type="number" domain={[0, max || 'auto']} tick={AXIS} allowDecimals={false} />
          <YAxis type="category" dataKey={nameKey} width={150} tick={AXIS} interval={0} />
          <Tooltip formatter={(value) => format(value)} />
          <Bar dataKey={valueKey} radius={[0, 6, 6, 0]} isAnimationActive={false}>
            {data.map((row, index) => <Cell key={row[nameKey] || index} fill={colors ? colors[index % colors.length] : row.color || color} />)}
            <LabelList dataKey={labelKey || valueKey} position="right" fontSize={11} fill="#101D36" formatter={labelKey ? undefined : format} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Barras verticales (una o varias series), opcionalmente apiladas.
export function VBars({ data, series, nameKey = 'name', stacked = false, height = 240, format = (value) => value }) {
  if (!hasValues(data, series.map((item) => item.key))) return <Empty />;
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: -12, right: 8, top: 16, bottom: 4 }}>
          <CartesianGrid vertical={false} stroke="#EEECE6" />
          <XAxis dataKey={nameKey} tick={AXIS} interval={0} angle={data.length > 3 ? -25 : 0} textAnchor={data.length > 3 ? 'end' : 'middle'} height={data.length > 3 ? 56 : 30} />
          <YAxis tick={AXIS} allowDecimals={false} />
          <Tooltip formatter={(value) => format(value)} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {series.map((item) => <Bar key={item.key} dataKey={item.key} name={item.label} fill={item.color} stackId={item.stack || (stacked ? 'stack' : undefined)} isAnimationActive={false} radius={stacked ? 0 : [4, 4, 0, 0]}>
            <LabelList dataKey={item.key} position={item.stack || stacked ? 'center' : 'top'} fontSize={10} fill={item.stack || stacked ? '#ffffff' : '#101D36'} formatter={(value) => (value ? format(value) : '')} />
          </Bar>)}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Lines({ data, series, nameKey = 'name', height = 220 }) {
  if (!hasValues(data, series.map((item) => item.key))) return <Empty />;
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ left: -12, right: 16, top: 16, bottom: 4 }}>
          <CartesianGrid vertical={false} stroke="#EEECE6" />
          <XAxis dataKey={nameKey} tick={AXIS} />
          <YAxis tick={AXIS} allowDecimals={false} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {series.map((item) => <Line key={item.key} type="monotone" dataKey={item.key} name={item.label} stroke={item.color} strokeWidth={2.5} dot={{ r: 4 }} isAnimationActive={false}><LabelList dataKey={item.key} position="top" fontSize={10} fill={item.color} /></Line>)}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// Dona con leyenda lateral que muestra etiqueta, valor y %.
export function Donut({ data, center }) {
  const total = (data || []).reduce((sum, item) => sum + (item.value || 0), 0);
  if (!total) return <Empty />;
  return (
    <div className="grid grid-cols-1 items-center gap-3 sm:grid-cols-[180px_minmax(0,1fr)]">
      <div className="relative mx-auto h-44 w-44">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart><Pie data={data} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} paddingAngle={1} isAnimationActive={false}>{data.map((item, index) => <Cell key={item.name} fill={item.color || PALETTE[index % PALETTE.length]} />)}</Pie><Tooltip /></PieChart>
        </ResponsiveContainer>
        {center && <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center"><span className="text-xl font-semibold text-[#101D36]">{center.value}</span><span className="text-[10px] text-slate-500">{center.label}</span></div>}
      </div>
      <ul className="space-y-1 text-sm">{data.map((item, index) => <li key={item.name} className="flex items-center justify-between gap-2"><span className="inline-flex min-w-0 items-center gap-2"><span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: item.color || PALETTE[index % PALETTE.length] }} /><span className="truncate">{item.name}</span></span><span className="shrink-0 font-semibold">{item.value} <span className="text-xs font-normal text-slate-500">({Math.round((item.value / total) * 100)}%)</span></span></li>)}</ul>
    </div>
  );
}

const SEMAPHORE = { verde: { label: 'Verde', color: COLORS.green, bg: '#ecfdf3' }, ambar: { label: 'Ámbar', color: COLORS.amber, bg: '#fffbeb' }, rojo: { label: 'Rojo', color: COLORS.red, bg: '#fef2f2' }, sin_datos: { label: 'Sin datos', color: COLORS.slate, bg: '#f8fafc' } };
export const semaphoreStyle = (key) => SEMAPHORE[key] || SEMAPHORE.sin_datos;

// Medidor: avance real vs meta con semáforo y texto (no solo color).
export function GoalBar({ item }) {
  const style = semaphoreStyle(item.semaphore);
  const shown = item.value == null ? 'Sin datos' : item.unit === 'ratio' ? `${Math.round(item.value * 100)}%` : item.value;
  const goal = item.unit === 'ratio' ? `${Math.round(item.goal * 100)}%` : item.goal;
  const width = item.progress == null ? 0 : Math.round(item.progress * 100);
  return (
    <div className="rounded-xl border p-3" style={{ borderColor: style.color, background: style.bg }} data-testid={`goal-${item.key}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2"><p className="text-sm font-semibold text-[#101D36]">{item.label}</p><span className="rounded-full px-2 py-0.5 text-xs font-bold text-white" style={{ background: style.color }}>{style.label}</span></div>
      <p className="mt-1 text-2xl font-semibold" style={{ color: style.color }}>{shown} <span className="text-xs font-normal text-slate-600">meta {goal}{item.goal_status === 'propuesta' ? ' (propuesta)' : ''}</span></p>
      <div className="mt-2 h-3 overflow-hidden rounded-full bg-white ring-1 ring-slate-200" role="progressbar" aria-valuenow={width} aria-valuemin={0} aria-valuemax={100} aria-label={`${item.label}: ${width}% de la meta`}><div className="h-full rounded-full" style={{ width: `${width}%`, background: style.color }} /></div>
      <p className="mt-1 text-[11px] text-slate-600">{item.progress == null ? 'Aún sin datos para medir.' : `${width}% de la meta · ${item.explanation}`}</p>
    </div>
  );
}
