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
  if (name.trim().length > 60 && words.length > 3) {
    let best = [1, 2];
    let smallestSpread = Number.POSITIVE_INFINITY;
    for (let first = 1; first < words.length - 1; first += 1) {
      for (let second = first + 1; second < words.length; second += 1) {
        const lengths = [words.slice(0, first), words.slice(first, second), words.slice(second)]
          .map((parts) => parts.join(' ').length);
        const spread = Math.max(...lengths) - Math.min(...lengths);
        if (spread < smallestSpread) {
          best = [first, second];
          smallestSpread = spread;
        }
      }
    }
    return [words.slice(0, best[0]).join(' '), words.slice(best[0], best[1]).join(' '), words.slice(best[1]).join(' ')];
  }
  let splitAt = 1;
  let smallestDifference = Number.POSITIVE_INFINITY;
  for (let index = 1; index < words.length; index += 1) {
    const first = words.slice(0, index).join(' ');
    const second = words.slice(index).join(' ');
    const difference = Math.abs(first.length - second.length);
    if (difference < smallestDifference) {
      splitAt = index;
      smallestDifference = difference;
    }
  }
  return [words.slice(0, splitAt).join(' '), words.slice(splitAt).join(' ')];
};