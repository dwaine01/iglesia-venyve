import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { MembershipCardBack, MembershipCardFront, MembershipCertificateTemplate } from './MembershipDocumentTemplates';
import { cardNameLines, formatMembershipDate, memberInitials, membershipDate, nameLengthClass } from './membershipDocumentUtils';
import { CR80, INSTITUTION, LETTER_LANDSCAPE } from './membershipDocumentGeometry';

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
  expect(cardNameLines('María Fernanda Rodríguez')).toEqual(['María Fernanda', 'Rodríguez']);
});

test('el carnet usa número oficial, fallback de foto y vencimiento condicional', () => {
  const front = renderToStaticMarkup(<MembershipCardFront data={data} photoSrc={null} />);
  const back = renderToStaticMarkup(<MembershipCardBack data={data} qrSrc="data:image/png;base64,qr" signatureSrc="blob:firma" />);
  expect(front).toContain('MIEMBRO ACTIVO');
  expect(front).toContain('VV-2026-0842');
  expect(front).toContain('LÍDER DE BIENVENIDA');
  expect(front).toContain('MF');
  expect(front).not.toContain('Válido hasta');
  expect(front).not.toContain('internal-uuid-never-visible');
  expect(front).not.toContain('data:image/png;base64,qr');
  expect(back).toContain('data:image/png;base64,qr');
  expect(back).toContain(INSTITUTION.legalName);
  expect(back).toContain(INSTITUTION.brandName);
  expect(back).toContain('614-508-0303');
  expect(back).toContain('blob:firma');
  expect(back).not.toContain('internal-uuid-never-visible');
});

test('el certificado incluye firma, QR y las tres referencias oficiales', () => {
  const certificate = renderToStaticMarkup(<MembershipCertificateTemplate data={data} signatureSrc="blob:firma" qrSrc="data:image/png;base64,qr" />);
  expect(certificate).toContain('CERTIFICADO DE MEMBRESÍA');
  expect(certificate).toContain('VV-2026-0842');
  expect(certificate).toContain('05-18-2014');
  expect(certificate).toContain('09-22-2026');
  expect(certificate).toContain('PASTORA PRINCIPAL');
  expect(certificate).toContain(INSTITUTION.legalName);
  expect(certificate).toContain(INSTITUTION.brandName);
  expect(certificate).not.toContain('internal-uuid-never-visible');
});

test('adapta nombre corto y fotografía sin inventar vencimiento', () => {
  const shortData = {
    ...data,
    person: { full_name: 'Ana Pérez' },
    membership: { ...data.membership, card_expiration_date: '2027-09-22' },
  };
  const front = renderToStaticMarkup(<MembershipCardFront data={shortData} photoSrc="blob:foto-horizontal" />);
  expect(front).toContain('font-size:5.1mm');
  expect(front).toContain('blob:foto-horizontal');
  expect(front).not.toContain('Válido hasta');
  expect(front).not.toContain('09-22-2027');
});

test('conserva las dimensiones físicas oficiales', () => {
  expect(CR80).toEqual({ width: 85.6, height: 53.98 });
  expect(LETTER_LANDSCAPE).toEqual({ width: 279.4, height: 215.9 });
});

test('reduce números extremos sin alterar las columnas físicas', () => {
  const extreme = { ...data, membership: { ...data.membership, member_number: 'VV-I52-XXXXXXXXXX-EXT' } };
  const card = renderToStaticMarkup(<MembershipCardFront data={extreme} photoSrc="photo.png" />);
  const certificate = renderToStaticMarkup(<MembershipCertificateTemplate data={extreme} signatureSrc="signature.png" qrSrc="qr.png" />);
  expect(card).toContain('font-size:1.55mm');
  expect(certificate).toContain('font-size:.075in');
});

test('balancea nombres compuestos en dos líneas sin truncar la identidad', () => {
  const longName = 'María Fernanda de los Ángeles Salazar Monteverde';
  const extreme = { ...data, person: { ...data.person, full_name: longName } };
  const card = renderToStaticMarkup(<MembershipCardFront data={extreme} photoSrc="photo.png" />);
  const certificate = renderToStaticMarkup(<MembershipCertificateTemplate data={extreme} signatureSrc="signature.png" qrSrc="qr.png" />);
  expect(card).toContain('María Fernanda de los');
  expect(card).toContain('Ángeles Salazar Monteverde');
  expect(card).toContain('font-size:2.25mm');
  expect(certificate).toContain('font-size:.52in');
  expect(certificate).toContain('white-space:nowrap');
});

test('usa tres líneas legibles solo para nombres excepcionales', () => {
  const name = 'María Fernanda de los Ángeles Santos Francisco Gómez Calderón del Valle';
  const extreme = { ...data, person: { ...data.person, full_name: name } };
  const card = renderToStaticMarkup(<MembershipCardFront data={extreme} photoSrc="photo.png" />);
  const certificate = renderToStaticMarkup(<MembershipCertificateTemplate data={extreme} signatureSrc="signature.png" qrSrc="qr.png" />);
  expect(card).toContain('font-size:2.2mm');
  expect(cardNameLines(name)).toHaveLength(3);
  expect(certificate).toContain('font-size:.34in');
  expect(certificate).toContain('white-space:normal');
});