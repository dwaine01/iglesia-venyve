import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { MembershipCardBack, MembershipCardFront, MembershipCertificateTemplate } from './MembershipDocumentTemplates';
import { formatMembershipDate, memberInitials, membershipDate, nameLengthClass } from './membershipDocumentUtils';

const data = {
  person: { full_name: 'María de los Ángeles Santos Francisco-Gómez', position: 'LÍDER DE BIENVENIDA' },
  membership: {
    membership_id: 'internal-uuid-never-visible',
    member_number: 'VV-2026-0842',
    status: 'active',
    historical_membership_date: '2014-05-18',
    card_expiration_date: null,
    certificate_issue_date: '2026-09-22',
  },
  certificate: { authorized_signer_name: 'Pastora Ana Martínez', authorized_signer_title: 'Pastora Principal' },
};

test('prioriza la fecha real de membresía y adapta nombres', () => {
  expect(membershipDate(data.membership)).toBe('2014-05-18');
  expect(formatMembershipDate('2014-05-18T12:30:00Z')).toBe('05-18-2014');
  expect(nameLengthClass(data.person.full_name)).toBe('document-name-long');
  expect(memberInitials('Ana Pérez')).toBe('AP');
});

test('el carnet usa número oficial, fallback de foto y vencimiento condicional', () => {
  const front = renderToStaticMarkup(<MembershipCardFront data={data} photoSrc={null} />);
  const back = renderToStaticMarkup(<MembershipCardBack data={data} qrSrc="data:image/png;base64,qr" />);
  expect(front).toContain('MIEMBRO ACTIVO');
  expect(front).toContain('VV-2026-0842');
  expect(front).toContain('MF');
  expect(front).not.toContain('Válido hasta');
  expect(front).not.toContain('internal-uuid-never-visible');
  expect(back).toContain('VV-2026-0842');
  expect(back).not.toContain('internal-uuid-never-visible');
});

test('el certificado incluye firma, QR y las tres referencias oficiales', () => {
  const certificate = renderToStaticMarkup(<MembershipCertificateTemplate data={data} signatureSrc="blob:firma" qrSrc="data:image/png;base64,qr" />);
  expect(certificate).toContain('CERTIFICADO DE MEMBRESÍA');
  expect(certificate).toContain('VV-2026-0842');
  expect(certificate).toContain('05-18-2014');
  expect(certificate).toContain('09-22-2026');
  expect(certificate).toContain('Pastora Ana Martínez');
  expect(certificate).not.toContain('internal-uuid-never-visible');
});