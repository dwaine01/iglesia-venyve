import React from 'react';

export const DedicationArtwork = ({ id }) => (
  <svg data-vv-art="dedication-certificate" viewBox="0 0 1056 816" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">
    <defs>
      <clipPath id={`${id}-clip`}><rect x="0" y="0" width="1056" height="816" rx="0" /></clipPath>
    </defs>
    <g clipPath={`url(#${id}-clip)`}>
      <rect x="0" y="0" width="1056" height="816" fill="var(--vd-cream)" />
      <path d="M0 0 C130 40 220 130 190 260 C160 380 40 380 0 340 Z" fill="var(--vd-sky)" opacity=".08" />
      <path d="M1056 816 C930 776 840 690 870 560 C900 440 1020 440 1056 480 Z" fill="var(--vd-lime)" opacity=".07" />
      <circle cx="90" cy="90" r="58" fill="none" stroke="var(--vd-sky)" strokeWidth="2" opacity=".35" />
      <circle cx="90" cy="90" r="40" fill="none" stroke="var(--vd-lime)" strokeWidth="1.4" opacity=".35" />
      <circle cx="966" cy="726" r="58" fill="none" stroke="var(--vd-lime)" strokeWidth="2" opacity=".35" />
      <circle cx="966" cy="726" r="40" fill="none" stroke="var(--vd-sky)" strokeWidth="1.4" opacity=".35" />
    </g>
    <rect x="20" y="20" width="1016" height="776" rx="18" ry="18" fill="none" stroke="var(--vd-sky-border)" strokeWidth="3" />
    <rect x="32" y="32" width="992" height="752" rx="14" ry="14" fill="none" stroke="var(--vd-lime-border)" strokeWidth="1.6" />
    <g transform="translate(478,118)" fill="none" stroke="var(--vd-navy)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" opacity=".85">
      <path d="M0 26 C10 6 34 -4 52 8 C60 2 72 4 76 14 C80 24 74 32 64 34 C56 44 30 46 16 34 C6 34 -4 30 0 26 Z" />
      <path d="M52 8 C58 -4 74 -8 84 0" />
      <circle cx="66" cy="18" r="2.6" fill="var(--vd-navy)" stroke="none" />
      <path d="M18 34 C12 44 4 48 -8 46" strokeWidth="1.8" opacity=".7" />
    </g>
  </svg>
);
