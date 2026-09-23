import React from 'react';

import './membership-documents.css';
import { CardBackArtwork, CardFrontArtwork } from './MembershipDocumentArtwork';
import { memberNameSize, membershipDocumentTokens, membershipNumberSize } from './MembershipDocumentTokens';
import { cardNameLines, formatMembershipDate, memberInitials, memberStatus, membershipDate } from './membershipDocumentUtils';
import { INSTITUTION, testIdFor } from './membershipDocumentGeometry';

const logoPath = '/assets/membership/church-logo.png';
const recognition = 'Al portador de este carnet se le reconoce como miembro activo de la Primera Iglesia del Nazareno “Ven y Ve”, con acceso a las actividades, servicios y beneficios de la congregación.';

const Brand = ({ rootId, exportMode }) => <>
  <img id={`${rootId}-logo`} data-vv-role="logo" src={logoPath} alt="Logo Ven y Ve" data-testid={testIdFor('membership-card-logo', exportMode)} />
  <div id={`${rootId}-brand`} data-vv-role="brand"><strong>PRIMERA IGLESIA DEL NAZARENO</strong><b>VEN Y VE</b><span>{INSTITUTION.tagline}</span></div>
</>;

export const MembershipCardFront = ({ data, photoSrc, exportMode = false }) => {
  const rootId = `vv-membership-card-front-${exportMode ? 'export' : 'preview'}`;
  const person = data?.person || {};
  const membership = data?.membership || {};
  return (
    <article id={rootId} data-vv-document="card-front" style={{ ...membershipDocumentTokens, boxShadow: exportMode ? 'none' : undefined }} data-testid={testIdFor('membership-card-front', exportMode)}>
      <CardFrontArtwork id={rootId} />
      <Brand rootId={rootId} exportMode={exportMode} />
      <div id={`${rootId}-photo`} data-vv-role="photo">
        {photoSrc ? <img src={photoSrc} alt={person.full_name} data-testid={testIdFor('membership-card-photo', exportMode)} /> : <span data-testid={testIdFor('membership-card-photo-fallback', exportMode)}>{memberInitials(person.full_name)}</span>}
      </div>
      <section id={`${rootId}-identity`} data-vv-role="identity">
        <p data-vv-role="kicker">CARNET OFICIAL DE MIEMBRO</p>
        <h2 data-vv-role="member-name" style={{ fontSize: memberNameSize(person.full_name) }} data-testid={testIdFor('membership-card-name', exportMode)}>{cardNameLines(person.full_name).map((line) => <span key={line}>{line}</span>)}</h2>
        <p data-vv-role="status" data-testid={testIdFor('membership-card-status', exportMode)}>{memberStatus(membership.status)}</p>
      </section>
      <dl id={`${rootId}-facts`} data-vv-role="facts">
        <div><dt>N.º DE MIEMBRO</dt><dd style={{ fontSize: membershipNumberSize(membership.member_number) }} data-testid={testIdFor('membership-member-number', exportMode)}>{membership.member_number || '—'}</dd></div>
        <div><dt>MIEMBRO DESDE</dt><dd data-testid={testIdFor('membership-card-member-since', exportMode)}>{formatMembershipDate(membershipDate(membership))}</dd></div>
      </dl>
    </article>
  );
};

export const MembershipCardBack = ({ data, qrSrc, signatureSrc, exportMode = false }) => {
  const rootId = `vv-membership-card-back-${exportMode ? 'export' : 'preview'}`;
  const membership = data?.membership || {};
  const certificate = data?.certificate || {};
  return (
    <article id={rootId} data-vv-document="card-back" style={{ ...membershipDocumentTokens, boxShadow: exportMode ? 'none' : undefined }} data-testid={testIdFor('membership-card-back', exportMode)}>
      <CardBackArtwork id={rootId} />
      <Brand rootId={rootId} exportMode={exportMode} />
      <section id={`${rootId}-message`} data-vv-role="message">
        <p data-testid={testIdFor('membership-card-recognition-message', exportMode)}>{recognition}</p><i aria-hidden="true" />
        <strong data-testid={testIdFor('membership-card-phone', exportMode)}>{INSTITUTION.phone}</strong><span>INFORMACIÓN INSTITUCIONAL</span>
      </section>
      <section id={`${rootId}-signature`} data-vv-role="signature">
        <div>{signatureSrc && <img src={signatureSrc} alt="Firma autorizada" data-testid={testIdFor('membership-card-signature-image', exportMode)} />}</div><i aria-hidden="true" />
        <strong data-testid={testIdFor('membership-card-signer-title', exportMode)}>{String(certificate.authorized_signer_title || 'PASTORA PRINCIPAL').toUpperCase()}</strong>
      </section>
      <section id={`${rootId}-verification`} data-vv-role="verification" data-testid={testIdFor('membership-card-verification', exportMode)}>
        <span>VERIFICACIÓN</span><strong style={{ fontSize: membershipNumberSize(membership.member_number, 'verification') }} data-testid={testIdFor('membership-card-qr-number', exportMode)}>{membership.member_number || '—'}</strong>
        <div data-vv-role="qr">{qrSrc && <img src={qrSrc} alt="QR de verificación" data-testid={testIdFor('membership-card-qr', exportMode)} />}</div>
        <b>ESCANEE PARA VALIDAR</b><small>Documento personal e intransferible</small>
      </section>
      <p id={`${rootId}-mission`} data-vv-role="mission">CONOCIENDO A DIOS<br />HACIENDO FAMILIA<br />TRANSFORMANDO VIDAS</p>
    </article>
  );
};