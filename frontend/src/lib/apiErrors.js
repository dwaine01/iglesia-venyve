export const apiErrorMessage = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const message = detail.map((item) => item?.msg).filter(Boolean).join(' · ');
    return message || fallback;
  }
  if (typeof detail?.message === 'string') return detail.message;
  return fallback;
};