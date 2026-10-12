export const formatUsdCents = (cents) => `$${(Number(cents || 0) / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const dollarsToCents = (value) => {
  const parsed = parseFloat(String(value).replace(',', '.'));
  if (!Number.isFinite(parsed) || parsed <= 0) return 0;
  return Math.round(parsed * 100);
};

export const normalizeSearchText = (text) => (text || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
