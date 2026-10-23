export const errorDetailText = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => item?.msg || String(item)).join(', ');
  const missing = Array.isArray(detail.missing) && detail.missing.length ? `: ${detail.missing.join(', ')}` : '';
  return `${detail.message || fallback}${missing}`;
};
