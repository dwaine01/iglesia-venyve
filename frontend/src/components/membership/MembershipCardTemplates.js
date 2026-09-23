import React from 'react';

import './membership-identity-documents.css';
import { cardNameLines, formatMembershipDate, memberInitials, memberStatus, membershipDate, nameLengthClass } from './membershipDocumentUtils';
import { INSTITUTION, testIdFor } from './membershipDocumentGeometry';

const logoPath = '/assets/membership/church-logo.png';
const recognitionMessage = 'Este documento acredita a su portador como miembro activo de la Primera Iglesia del Nazareno Ven y Ve y es personal e intransferible.';

const CardBrand = ({ exportMode = false, label }) => (
  <header className="card-brand" data-testid={testIdFor('membership-institution-brand', exportMode)}>
    <img className="card-brand-logo" src={logoPath} alt="Primera Iglesia del Nazareno Ven y Ve" data-testid={testIdFor('membership-card-logo', exportMode)} />
    <div className="card-brand-copy">
      <strong>{INSTITUTION.fullName}</strong>
      <span>{label}</span>
    </div>
  </header>
);

export const MembershipCardFront = ({ data, photoSrc, qrSrc, exportMode = false }) => {
  const person = data?.person || {};
  const membership = data?.membership || {};
  const nameLines = cardNameLines(person.full_name);
  return (
    <article className={`design-locked-document membership-card membership-card-front ${exportMode ? 'document-export' : ''}`} data-testid={testIdFor('membership-card-front', exportMode)}>
      <CardBrand exportMode={exportMode} label="CARNET OFICIAL DE MIEMBRO" />
      <div className="card-front-grid">
        <div className="card-photo-frame">
          {photoSrc ? <img src={photoSrc} alt={person.full_name} data-testid={testIdFor('membership-card-photo', exportMode)} /> : <span className="card-photo-fallback" data-testid={testIdFor('membership-card-photo-fallback', exportMode)}>{memberInitials(person.full_name)}</span>}
        </div>
        <section className="card-member-copy">
          <p className="card-document-kicker" data-testid={testIdFor('membership-card-status', exportMode)}>{memberStatus(membership.status)}</p>
          <h2 className={`card-member-name ${nameLengthClass(person.full_name)}`} data-testid={testIdFor('membership-card-name', exportMode)}>
            {nameLines.map((line) => <span key={line}>{line}</span>)}
          </h2>
          <p className="card-member-position" data-testid={testIdFor('membership-card-position', exportMode)}>{person.position || 'MIEMBRO'}</p>
          <dl className="card-member-facts">
            <div><dt>N.º DE MIEMBRO</dt><dd data-testid={testIdFor('membership-member-number', exportMode)}>{membership.member_number || '—'}</dd></div>
            <div><dt>MIEMBRO DESDE</dt><dd data-testid={testIdFor('membership-card-member-since', exportMode)}>{formatMembershipDate(membershipDate(membership))}</dd></div>
          </dl>
        </section>
        <section className="card-front-verification" data-testid={testIdFor('membership-card-verification', exportMode)}>
          <div className="card-qr-safe-zone">{qrSrc && <img src={qrSrc} alt="QR de verificación" data-testid={testIdFor('membership-card-qr', exportMode)} />}</div>
          <strong data-testid={testIdFor('membership-card-qr-number', exportMode)}>{membership.member_number || '—'}</strong>
          <span>ESCANEE PARA VALIDAR</span>
        </section>
      </div>
      <div className="card-color-rule" aria-hidden="true"><i /><i /></div>
    </article>
  );
};

export const MembershipCardBack = ({ data, signatureSrc, exportMode = false }) => {
  const certificate = data?.certificate || {};
  return (
    <article className={`design-locked-document membership-card membership-card-back ${exportMode ? 'document-export' : ''}`} data-testid={testIdFor('membership-card-back', exportMode)}>
      <CardBrand exportMode={exportMode} label={INSTITUTION.tagline} />
      <div className="card-back-grid">
        <section className="card-back-recognition">
          <p data-testid={testIdFor('membership-card-recognition-message', exportMode)}>{recognitionMessage}</p>
          <div className="card-back-contact"><strong data-testid={testIdFor('membership-card-phone', exportMode)}>{INSTITUTION.phone}</strong><span>INFORMACIÓN INSTITUCIONAL</span></div>
        </section>
        <section className="card-back-official">
          <div className="card-back-signature-image">
            {signatureSrc ? <img src={signatureSrc} alt="Firma autorizada" data-testid={testIdFor('membership-card-signature-image', exportMode)} /> : <span data-testid={testIdFor('membership-card-signature-missing', exportMode)}>Firma no configurada</span>}
          </div>
          <i className="card-back-signature-line" aria-hidden="true" />
          <strong data-testid={testIdFor('membership-card-signer-title', exportMode)}>{String(certificate.authorized_signer_title || 'PASTORA PRINCIPAL').toUpperCase()}</strong>
          <small data-testid={testIdFor('membership-card-signer-name', exportMode)}>{certificate.authorized_signer_name || INSTITUTION.fullName}</small>
        </section>
      </div>
      <footer className="card-back-footer"><span>Documento personal e intransferible</span><strong>{INSTITUTION.mission}</strong></footer>
    </article>
  );
};