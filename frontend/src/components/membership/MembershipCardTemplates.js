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

const CardBrand = ({ dark = false }) => (
  <div className={`official-card-brand ${dark ? 'official-card-brand-dark' : ''}`}>
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
      <div className="card-front-brand-field" aria-hidden="true" />
      <div className="card-front-brand-accent" aria-hidden="true" />
      <CardBrand />
      <section className="card-front-identity">
        <p className="card-document-label">CARNET OFICIAL DE MIEMBRO</p>
        <h2 className={nameLengthClass(person.full_name)} data-testid="membership-card-name">{person.full_name}</h2>
        <p className="card-active-badge" data-testid="membership-card-status"><i />{memberStatus(membership.status)}</p>
        <dl className={`card-facts ${expires ? 'card-facts-with-expiry' : ''}`}>
          <div><dt>Número oficial</dt><dd data-testid="membership-member-number">{membership.member_number || '—'}</dd></div>
          <div><dt>Miembro desde</dt><dd data-testid="membership-card-member-since">{formatMembershipDate(membershipDate(membership))}</dd></div>
          {expires && <div><dt>Válido hasta</dt><dd data-testid="membership-card-expires">{formatMembershipDate(expires)}</dd></div>}
        </dl>
      </section>
      <div className="card-front-photo-frame">
        {photoSrc ? <img src={photoSrc} alt={person.full_name} data-testid="membership-card-photo" /> : <span data-testid="membership-card-photo-fallback">{memberInitials(person.full_name)}</span>}
      </div>
      <p className="card-front-microtext">CREDENCIAL INSTITUCIONAL</p>
    </article>
  );
};

export const MembershipCardBack = ({ data, qrSrc, exportMode = false }) => {
  const person = data?.person || {};
  const membership = data?.membership || {};
  return (
    <article className={`membership-card membership-card-back ${exportMode ? 'document-export' : ''}`} data-testid="membership-card-back">
      <div className="card-back-accent" aria-hidden="true" />
      <section className="card-back-copy">
        <CardBrand dark />
        <p className="card-back-eyebrow">VERIFICACIÓN DE MEMBRESÍA</p>
        <strong className="card-back-number" data-testid="membership-card-back-number">{membership.member_number || '—'}</strong>
        <h2 data-testid="membership-card-back-name">{person.full_name}</h2>
        <div className="card-back-rule" aria-hidden="true" />
        <p className="card-verification-copy">Escanee el código para validar la autenticidad y vigencia de esta membresía.</p>
        <p className="card-back-institution">CASA DE ORACIÓN VEN Y VE</p>
      </section>
      <section className="card-qr-panel">
        <div className="card-qr-safe-zone">{qrSrc && <img src={qrSrc} alt="QR de verificación" data-testid="membership-card-qr" />}</div>
        <strong>VERIFICACIÓN DIGITAL</strong>
      </section>
    </article>
  );
};