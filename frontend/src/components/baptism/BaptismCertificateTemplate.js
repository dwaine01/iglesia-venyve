import React from 'react';

import './baptism-documents.css';
import { CertificateArtwork } from '../membership/MembershipDocumentArtwork';
import { memberNameSize, membershipDocumentTokens } from '../membership/MembershipDocumentTokens';
import { formatMembershipDate } from '../membership/membershipDocumentUtils';
import { INSTITUTION, testIdFor } from '../membership/membershipDocumentGeometry';

const logoPath = '/assets/membership/church-logo.png';
const statement = 'ha sido bautizado(a) en las aguas, en obediencia a la Palabra de Dios y como testimonio público de su fe en Jesucristo, en la Primera Iglesia del Nazareno Ven y Ve.';

export const BaptismCertificateTemplate = ({ data, signatureSrc, qrSrc, exportMode = false }) => {
  const rootId = `vv-baptism-certificate-${exportMode ? 'export' : 'preview'}`;
  const person = data?.person || {};
  const baptism = data?.baptism || {};
  const certificate = data?.certificate || {};
  const wrapsName = String(person.full_name || '').trim().length > 48;
  return (
    <article id={rootId} data-vv-document="baptism-certificate" style={{ ...membershipDocumentTokens, boxShadow: exportMode ? 'none' : undefined }} data-testid={testIdFor('baptism-certificate-template', exportMode)}>
      <CertificateArtwork id={rootId} />
      <img id={`${rootId}-logo`} data-vv-role="logo" src={logoPath} alt="Logo Ven y Ve" data-testid={testIdFor('baptism-certificate-logo', exportMode)} />
      <div id={`${rootId}-brand`} data-vv-role="brand"><strong>PRIMERA IGLESIA DEL NAZARENO</strong><b>VEN Y VE</b><span>{INSTITUTION.tagline}</span></div>
      <h1 id={`${rootId}-title`} data-vv-role="title">CERTIFICADO DE BAUTISMO</h1>
      <i id={`${rootId}-title-rule`} data-vv-role="title-rule" aria-hidden="true" />
      <p id={`${rootId}-recognition`} data-vv-role="recognition">Se certifica que</p>
      <h2 id={`${rootId}-name`} data-vv-role="member-name" style={{ fontSize: memberNameSize(person.full_name, 'certificate'), whiteSpace: wrapsName ? 'normal' : 'nowrap', top: wrapsName ? '3.34in' : '3.30in', height: wrapsName ? '1.06in' : '1.0in', lineHeight: wrapsName ? .92 : 1.15, display: wrapsName ? '-webkit-box' : 'block', WebkitLineClamp: wrapsName ? 3 : undefined, WebkitBoxOrient: wrapsName ? 'vertical' : undefined, overflow: 'hidden', textOverflow: 'ellipsis' }} data-testid={testIdFor('baptism-certificate-member-name', exportMode)}>{person.full_name}</h2>
      <p id={`${rootId}-statement`} data-vv-role="statement" data-testid={testIdFor('baptism-certificate-statement', exportMode)}>{statement}</p>
      <dl id={`${rootId}-facts`} data-vv-role="facts" data-testid={testIdFor('baptism-certificate-facts', exportMode)}>
        <div><dt>BAUTIZADO EL</dt><dd data-testid={testIdFor('baptism-certificate-date', exportMode)}>{formatMembershipDate(baptism.baptism_date)}</dd></div>
        <div><dt>LUGAR</dt><dd data-testid={testIdFor('baptism-certificate-location', exportMode)}>{baptism.location || baptism.church_name || '—'}</dd></div>
        <div><dt>FECHA DE EMISIÓN</dt><dd data-testid={testIdFor('baptism-certificate-issue-date', exportMode)}>{formatMembershipDate(baptism.certificate_issue_date)}</dd></div>
      </dl>
      <section id={`${rootId}-signature`} data-vv-role="signature">
        <div>{signatureSrc && <img src={signatureSrc} alt="Firma autorizada" data-testid={testIdFor('baptism-certificate-signature-image', exportMode)} />}</div><i aria-hidden="true" />
        <strong data-testid={testIdFor('baptism-certificate-signer-title', exportMode)}>MINISTRO OFICIANTE</strong>
        <small data-testid={testIdFor('baptism-certificate-signer-name', exportMode)}>{certificate.officiant_name || INSTITUTION.fullName}</small>
      </section>
      <section id={`${rootId}-verification`} data-vv-role="verification">
        <div data-vv-role="qr">{qrSrc && <img src={qrSrc} alt="QR de verificación oficial" data-testid={testIdFor('baptism-certificate-qr', exportMode)} />}</div><strong>VERIFICACIÓN DIGITAL</strong>
      </section>
      <p id={`${rootId}-mission`} data-vv-role="mission"><i />CONOCIENDO A DIOS&nbsp;&nbsp; · &nbsp;&nbsp;HACIENDO FAMILIA&nbsp;&nbsp; · &nbsp;&nbsp;TRANSFORMANDO VIDAS<i /></p>
    </article>
  );
};
