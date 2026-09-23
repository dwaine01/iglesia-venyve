export const formatMembershipDate = (value) => {
  if (!value) return '—';
  const [year, month, day] = String(value).slice(0, 10).split('-');
  return `${month}-${day}-${year}`;
};

export const membershipDate = (membership = {}) => (
  membership.historical_membership_date
  || membership.acceptance_signed_at
  || membership.regularized_at
  || membership.activated_at
  || membership.created_at
  || null
);

export const memberStatus = (status) => (
  status === 'active' ? 'MIEMBRO ACTIVO' : String(status || 'MIEMBRO').replaceAll('_', ' ').toUpperCase()
);

export const memberInitials = (name = '') => {
  const particles = new Set(['de', 'del', 'la', 'las', 'los', 'y']);
  const words = name.split(/\s+/).filter((part) => part && !particles.has(part.toLowerCase()));
  const selected = words.length > 1 ? [words[0], words[words.length - 1]] : words;
  return selected.map((part) => part[0]).join('').toUpperCase() || 'VV';
};

export const nameLengthClass = (name = '') => {
  if (name.length > 52) return 'document-name-extra-long';
  if (name.length > 38) return 'document-name-long';
  if (name.length > 27) return 'document-name-medium';
  return 'document-name-short';
};

export const cardNameLines = (name = '') => {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length < 3) return [name.trim() || '—'];
  return [words.slice(0, -1).join(' '), words.at(-1)];
};