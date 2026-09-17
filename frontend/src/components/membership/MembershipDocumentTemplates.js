import React from 'react';

import './membership-documents.css';
import './membership-document-overrides.css';

const logoPath = '/assets/membership/church-logo.png';

export const formatMembershipDate = (value) => {
  if (!value) return '—';
  const [year, month, day] = String(value).slice(0, 10).split('-');
  return `${month}-${day}-${year}`;
};

const nameSize = (name, base, medium, small) => {
  const length = (name || '').length;
  if (length > 34) return small;
  if (length > 24) return medium;
  return base;
};

export const MembershipCertificateTemplate = ({ data, signatureSrc, exportMode = false }) => {
  const person = data?.person || {};
  const membership = data?.membership || {};
  const certificate = data?.certificate || {};
  return <div className={`membership-certificate ${exportMode ? 'document-export' : ''}`} data-testid="membership-certificate-template">
    <div className="certificate-frame" />
    <div className="certificate-left-rail"><div className="certificate-rail-blue" /><div className="certificate-rail-green" /></div>
    <img src={logoPath} alt="Casa de Oración Ven y Ve" className="certificate-logo" />
    <img src={logoPath} alt="" className="certificate-watermark" aria-hidden="true" />
    <main className="certificate-content">
      <p className="certificate-church">CASA DE ORACIÓN VEN Y VE</p>
      <p className="certificate-kicker">RECONOCIMIENTO OFICIAL DE MEMBRESÍA</p>
      <h2>CERTIFICADO</h2>
      <h3>DE MIEMBRO</h3>
      <div className="certificate-rule" />
      <p className="certificate-presents">Se certifica que</p>
      <p className="certificate-name" style={{ fontSize: nameSize(person.full_name, '5.6cqw', '4.7cqw', '3.9cqw') }} data-testid="certificate-member-name">{person.full_name}</p>
      <p className="certificate-verse">“Porque yo sé los pensamientos que tengo acerca de vosotros, dice Jehová,<br />pensamientos de paz, y no de mal, para daros el fin que esperáis.”</p>
      <p className="certificate-reference">JEREMÍAS 29:11</p>
      <div className="certificate-signature-block">
        <div className="certificate-signature-line">{signatureSrc && <img src={signatureSrc} alt="Firma autorizada" data-testid="certificate-signature-image" />}</div>
        <strong>{certificate.authorized_signer_name || 'Firma autorizada'}</strong>
        <span>{certificate.authorized_signer_title || 'Casa de Oración Ven y Ve'}</span>
      </div>
      <div className="certificate-date-block"><strong data-testid="certificate-issue-date">{formatMembershipDate(membership.certificate_issue_date)}</strong><span>FECHA DE EMISIÓN</span></div>
    </main>
  </div>;
};

export const MembershipCardFront = ({ data, photoSrc, exportMode = false }) => {
  const person = data?.person || {};
  const membership = data?.membership || {};
  return <div className={`membership-card membership-card-front ${exportMode ? 'document-export' : ''}`} data-testid="membership-card-front">
    <div className="card-front-rail" /><div className="card-front-blue-angle" /><div className="card-front-green-angle" />
    <div className="card-photo-wrap">{photoSrc ? <img src={photoSrc} alt={person.full_name} data-testid="membership-card-photo" /> : <span>{(person.full_name || 'M').split(' ').map((part) => part[0]).slice(0, 2).join('')}</span>}</div>
    <img src={logoPath} alt="Casa de Oración Ven y Ve" className="card-logo" />
    <div className="card-member-number"><span>MEMBER NO.</span><strong data-testid="membership-member-number">{membership.member_number || '—'}</strong></div>
    <div className="card-identity"><p className="card-name" style={{ fontSize: nameSize(person.full_name, '4.7cqw', '3.8cqw', '2.65cqw') }} data-testid="membership-card-name">{person.full_name}</p><p className="card-position" data-testid="membership-card-position">{person.position || 'MIEMBRO'}</p></div>
    <div className="card-dates"><p><span>ISSUED</span><strong data-testid="membership-card-issued">{formatMembershipDate(membership.card_issue_date)}</strong></p><p><span>EXPIRES</span><strong data-testid="membership-card-expires">{formatMembershipDate(membership.card_expiration_date)}</strong></p></div>
    <p className="card-status-label">CARNET OFICIAL DE MIEMBRO</p>
  </div>;
};

export const MembershipCardBack = ({ data, qrSrc, exportMode = false }) => {
  const person = data?.person || {};
  const membership = data?.membership || {};
  return <div className={`membership-card membership-card-back ${exportMode ? 'document-export' : ''}`} data-testid="membership-card-back">
    <div className="card-back-blue" /><div className="card-back-green" />
    <img src={logoPath} alt="Casa de Oración Ven y Ve" className="card-back-logo" />
    <div className="card-back-copy"><p>IDENTIFICACIÓN DE MEMBRESÍA</p><strong data-testid="membership-card-back-name">{person.full_name}</strong><span>{person.position || 'MIEMBRO'}</span><small>Este carnet es personal. Escanee el código para verificar su vigencia en VEN Y VE 360.</small></div>
    <div className="card-qr-wrap">{qrSrc && <img src={qrSrc} alt="QR de verificación" data-testid="membership-card-qr" />}<span>VERIFICAR</span></div>
    <div className="card-back-footer"><span>MEMBER NO. {membership.member_number}</span><span>VÁLIDO HASTA {formatMembershipDate(membership.card_expiration_date)}</span></div>
  </div>;
};