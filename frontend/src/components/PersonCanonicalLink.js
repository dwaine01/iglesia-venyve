import React from 'react';
import { Link } from 'react-router-dom';

/** Canonical navigation primitive mandated by ONE PERSON → ONE PROFILE 360. */
export default function PersonCanonicalLink({ personId, children, className = '', ...props }) {
  if (!personId) return <span className={className}>{children}</span>;
  return (
    <Link
      to={`/personas/${personId}`}
      className={`transition-colors hover:text-[#8A6D2F] hover:underline ${className}`}
      {...props}
    >
      {children}
    </Link>
  );
}
