import React from 'react';

import './membership-documents.css';
import {
  formatMembershipDate,
  memberInitials,
  memberStatus,
  membershipDate,
  nameLengthClass,
} from './membershipDocumentUtils';

const logoPath = '/assets/membership/church-logo.png';

const CardBrand = ({ compact = false }) => (
  <div className={compact ? 'card-brand card-brand-compact' : 'card-brand'}>
    <img src={logoPath} alt="Casa de Oración Ven y Ve" />
    <div><span>Casa de Oración</span><strong>VEN Y VE</strong></div>
  </div>
);

export const MembershipCardFront = ({ data, photoSrc, exportMode = false }) => {
  const person = data?.person || {};
  const membership = data?.membership || {};
  const expires = membership.card_expiration_date;
  return (
    <article className={`membership-card membership-card-front ${exportMode ? 'document-export' : ''}`} data-testid="membership-card-front">
      <div className="card-top-rule" aria-hidden="true" />
      <CardBrand />
      <div className="card-photo-column">
        <div className="card-photo-frame">
          {photoSrc ? <img src={photoSrc} alt={person.full_name} data-testid="membership-card-photo" /> : <span data-testid="membership-card-photo-fallback">{memberInitials(person.full_name)}</span>}
        </div>
        <p className="card-active-badge" data-testid="membership-card-status"><i />{memberStatus(membership.status)}</p>
      </div>
      <div className="card-identity-panel">
        <p className="card-document-label">CARNET OFICIAL DE MIEMBRO</p>
        <h2 className={nameLengthClass(person.full_name)} data-testid="membership-card-name">{person.full_name}</h2>
        {person.position && person.position !== 'MIEMBRO' && <p className="card-position" data-testid="membership-card-position">{person.position}</p>}
        <dl className={`card-facts ${expires ? '' : 'card-facts-no-expiry'}`}>
          <div className="card-fact-number"><dt>Nº oficial de miembro</dt><dd data-testid="membership-member-number">{membership.member_number || '—'}</dd></div>
          <div><dt>Miembro desde</dt><dd data-testid="membership-card-member-since">{formatMembershipDate(membershipDate(membership))}</dd></div>
          {expires && <div><dt>Válido hasta</dt><dd data-testid="membership-card-expires">{formatMembershipDate(expires)}</dd></div>}
        </dl>
      </div>
      <div className="card-bottom-mark" aria-hidden="true"><span /><i /></div>
    </article>
  );
};

export const MembershipCardBack = ({ data, qrSrc, exportMode = false }) => {
  const person = data?.person || {};
  const membership = data?.membership || {};
  return (
    <article className={`membership-card membership-card-back ${exportMode ? 'document-export' : ''}`} data-testid="membership-card-back">
      <img src={logoPath} alt="" className="card-back-watermark" aria-hidden="true" />
      <section className="card-back-copy">
        <CardBrand compact />
        <p className="card-back-eyebrow">IDENTIFICACIÓN OFICIAL DE MEMBRESÍA</p>
        <h2 data-testid="membership-card-back-name">{person.full_name}</h2>
        <p className="card-back-number"><span>Nº DE MIEMBRO</span><strong data-testid="membership-card-back-number">{membership.member_number || '—'}</strong></p>
        <p className="card-verification-copy">Este carnet es personal e intransferible. Escanee el código para confirmar su autenticidad y vigencia en VEN Y VE 360.</p>
      </section>
      <section className="card-qr-panel">
        <div className="card-qr-safe-zone">{qrSrc && <img src={qrSrc} alt="QR de verificación" data-testid="membership-card-qr" />}</div>
        <strong>VERIFICACIÓN DIGITAL</strong>
        <span>Escanee para validar</span>
      </section>
      <footer className="card-back-footer">“Vosotros, pues, sois el cuerpo de Cristo” <strong>· 1 CORINTIOS 12:27</strong></footer>
    </article>
  );
};