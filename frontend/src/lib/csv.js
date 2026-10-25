import { toast } from 'sonner';

// CSV para Excel (BOM para que abra los acentos bien).
export function downloadCsv(filename, rows) {
  if (!rows?.length) { toast.message('No hay datos para exportar'); return; }
  const headers = Object.keys(rows[0]);
  const escape = (value) => { const text = value == null ? '' : String(value); return /[",\n;]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text; };
  const csv = [headers.join(','), ...rows.map((row) => headers.map((key) => escape(row[key])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}
