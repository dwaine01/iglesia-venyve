import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { MembershipCardBack, MembershipCardFront, MembershipCertificateTemplate } from './MembershipDocumentTemplates';

const root = path.resolve(__dirname, '../../../..');
const sha256 = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const fixture = {
  person: { full_name: 'María Fernanda Rodríguez', position: 'MIEMBRO' },
  membership: {
    member_number: 'VV-0284', status: 'active', historical_membership_date: '2014-05-18',
    certificate_issue_date: '2026-09-22',
  },
};

test('master visual y archivos DESIGN LOCKED conservan sus hashes aprobados', () => {
  const files = [
    'design-reference/membership-documents-master.png',
    'frontend/public/assets/membership/church-logo.png',
    'frontend/src/assets/fonts/PlusJakartaSans-Variable.ttf',
    'frontend/src/assets/fonts/CormorantGaramond-Variable.ttf',
    'frontend/src/assets/fonts/CormorantGaramond-Italic-Variable.ttf',
    'frontend/src/components/membership/membershipDocumentGeometry.js',
    'frontend/src/components/membership/MembershipDocumentArtwork.js',
    'frontend/src/components/membership/MembershipDocumentTokens.js',
    'frontend/src/components/membership/membership-documents.css',
    'frontend/src/components/membership/MembershipCardTemplates.js',
    'frontend/src/components/membership/MembershipCertificateTemplate.js',
    'frontend/src/components/membership/membershipPdf.js',
  ];
  expect(Object.fromEntries(files.map((file) => [file, sha256(path.join(root, file))]))).toMatchSnapshot();
});

test('golden estructural del carnet frente', () => {
  expect(renderToStaticMarkup(<MembershipCardFront data={fixture} photoSrc="golden-photo.jpg" />)).toMatchSnapshot();
});

test('golden estructural del carnet reverso', () => {
  expect(renderToStaticMarkup(<MembershipCardBack data={fixture} qrSrc="golden-qr.png" signatureSrc="golden-signature.png" />)).toMatchSnapshot();
});

test('golden estructural del certificado', () => {
  expect(renderToStaticMarkup(<MembershipCertificateTemplate data={fixture} qrSrc="golden-qr.png" signatureSrc="golden-signature.png" />)).toMatchSnapshot();
});