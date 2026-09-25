import React from 'react';

import './membership-documents.css';
import { CertificateArtwork } from './MembershipDocumentArtwork';
import { memberNameSize, membershipDocumentTokens, membershipNumberSize } from './MembershipDocumentTokens';
import { formatMembershipDate, membershipDate } from './membershipDocumentUtils';
import { INSTITUTION, testIdFor } from './membershipDocumentGeometry';

const logoPath = '/assets/membership/church-logo.png';
const statement = 'ha sido recibido(a) como miembro activo de la Primera Iglesia del Nazareno Ven y Ve, confirmando su compromiso con la visión, los valores y la misión de nuestra iglesia.';

export const MembershipCertificateTemplate = ({ data, signatureSrc, qrSrc, exportMode = false }) => {
  const rootId = `vv-membership-certificate-${exportMode ? 'export' : 'preview'}`;
  const person = data?.person || {};
  const membership = data?.membership || {};
  const certificate = data?.certificate || {};
  const wrapsName = String(person.full_name || '').trim().length > 48;
  return (
    <article id={rootId} data-vv-document="certificate" style={{ ...membershipDocumentTokens, boxShadow: exportMode ? 'none' : undefined }} data-testid={testIdFor('membership-certificate-template', exportMode)}>
      <CertificateArtwork id={rootId} />
      <img id={`${rootId}-logo`} data-vv-role="logo" src={logoPath} alt="Logo Ven y Ve" data-testid={testIdFor('certificate-logo', exportMode)} />
      <div id={`${rootId}-brand`} data-vv-role="brand"><strong>PRIMERA IGLESIA DEL NAZARENO</strong><b>VEN Y VE</b><span>{INSTITUTION.tagline}</span></div>
      <h1 id={`${rootId}-title`} data-vv-role="title">CERTIFICADO DE MEMBRESÍA</h1>
      <i id={`${rootId}-title-rule`} data-vv-role="title-rule" aria-hidden="true" />
      <p id={`${rootId}-recognition`} data-vv-role="recognition">Se certifica que</p>
      <h2 id={`${rootId}-name`} data-vv-role="member-name" style={{ fontSize: memberNameSize(person.full_name, 'certificate'), whiteSpace: wrapsName ? 'normal' : 'nowrap', top: wrapsName ? '3.34in' : '3.325in', height: wrapsName ? '1.06in' : '.81in', lineHeight: wrapsName ? .92 : 1, display: wrapsName ? '-webkit-box' : 'block', WebkitLineClamp: wrapsName ? 3 : undefined, WebkitBoxOrient: wrapsName ? 'vertical' : undefined, overflow: 'hidden', textOverflow: 'ellipsis' }} data-testid={testIdFor('certificate-member-name', exportMode)}>{person.full_name}</h2>
      <p id={`${rootId}-statement`} data-vv-role="statement" data-testid={testIdFor('certificate-membership-statement', exportMode)}>{statement}</p>
      <dl id={`${rootId}-facts`} data-vv-role="facts" data-testid={testIdFor('certificate-official-data', exportMode)}>
        <div><dt>N.º DE MIEMBRO</dt><dd style={{ fontSize: membershipNumberSize(membership.member_number, 'certificate') }} data-testid={testIdFor('certificate-member-number', exportMode)}>{membership.member_number || '—'}</dd></div>
        <div><dt>MIEMBRO DESDE</dt><dd data-testid={testIdFor('certificate-membership-date', exportMode)}>{formatMembershipDate(membershipDate(membership))}</dd></div>
        <div><dt>FECHA DE EMISIÓN</dt><dd data-testid={testIdFor('certificate-issue-date', exportMode)}>{formatMembershipDate(membership.certificate_issue_date)}</dd></div>
      </dl>
      <section id={`${rootId}-signature`} data-vv-role="signature">
        <div>{signatureSrc && <img src={signatureSrc} alt="Firma autorizada" data-testid={testIdFor('certificate-signature-image', exportMode)} />}</div><i aria-hidden="true" />
        <strong data-testid={testIdFor('certificate-signer-title', exportMode)}>{String(certificate.authorized_signer_title || 'PASTORA PRINCIPAL').toUpperCase()}</strong>
        <small data-testid={testIdFor('certificate-signer-name', exportMode)}>{certificate.authorized_signer_name || INSTITUTION.fullName}</small>
      </section>
      <section id={`${rootId}-verification`} data-vv-role="verification">
        <div data-vv-role="qr">{qrSrc && <img src={qrSrc} alt="QR de verificación oficial" data-testid={testIdFor('certificate-qr', exportMode)} />}</div><strong>VERIFICACIÓN DIGITAL</strong>
      </section>
      <p id={`${rootId}-mission`} data-vv-role="mission"><i />CONOCIENDO A DIOS&nbsp;&nbsp; · &nbsp;&nbsp;HACIENDO FAMILIA&nbsp;&nbsp; · &nbsp;&nbsp;TRANSFORMANDO VIDAS<i /></p>
    </article>
  );
};