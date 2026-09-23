import React from 'react';

import './membership-identity-documents.css';
import { formatMembershipDate, membershipDate, nameLengthClass } from './membershipDocumentUtils';
import { INSTITUTION, testIdFor } from './membershipDocumentGeometry';

const logoPath = '/assets/membership/church-logo.png';
const statement = 'ha sido recibido(a) como miembro activo de la Primera Iglesia del Nazareno Ven y Ve, en reconocimiento de su compromiso con la fe, la comunión y el servicio.';

export const MembershipCertificateTemplate = ({ data, signatureSrc, qrSrc, exportMode = false }) => {
  const person = data?.person || {};
  const membership = data?.membership || {};
  const certificate = data?.certificate || {};
  return (
    <article className={`design-locked-document membership-certificate ${exportMode ? 'document-export' : ''}`} data-testid={testIdFor('membership-certificate-template', exportMode)}>
      {['top-left', 'top-right', 'bottom-left', 'bottom-right'].map((corner) => <i key={corner} className={`certificate-corner-accent ${corner}`} aria-hidden="true" />)}
      <header className="certificate-header" data-testid={testIdFor('certificate-institution-brand', exportMode)}>
        <img className="certificate-logo" src={logoPath} alt="Primera Iglesia del Nazareno Ven y Ve" data-testid={testIdFor('certificate-logo', exportMode)} />
        <p className="certificate-legal-name">{INSTITUTION.fullName}</p>
      </header>
      <main className="certificate-main">
        <h1 className="certificate-title">CERTIFICADO DE MEMBRESÍA</h1>
        <div className="certificate-title-rule" aria-hidden="true"><i /><i /></div>
        <p className="certificate-recognition">Se certifica que</p>
        <h2 className={`certificate-member-name ${nameLengthClass(person.full_name)}`} data-testid={testIdFor('certificate-member-name', exportMode)}>{person.full_name}</h2>
        <p className="certificate-statement" data-testid={testIdFor('certificate-membership-statement', exportMode)}>{statement}</p>
      </main>
      <div className="certificate-footer-grid">
        <section className="certificate-signature">
          <div className="certificate-signature-image">{signatureSrc ? <img src={signatureSrc} alt="Firma autorizada" data-testid={testIdFor('certificate-signature-image', exportMode)} /> : <span data-testid={testIdFor('certificate-signature-missing', exportMode)}>Firma no configurada</span>}</div>
          <i className="certificate-signature-line" aria-hidden="true" />
          <strong data-testid={testIdFor('certificate-signer-title', exportMode)}>{String(certificate.authorized_signer_title || 'PASTORA PRINCIPAL').toUpperCase()}</strong>
          <small data-testid={testIdFor('certificate-signer-name', exportMode)}>{certificate.authorized_signer_name || INSTITUTION.fullName}</small>
        </section>
        <section className="certificate-data-grid" data-testid={testIdFor('certificate-official-data', exportMode)}>
          <div className="certificate-data-item"><span>N.º DE MIEMBRO</span><strong data-testid={testIdFor('certificate-member-number', exportMode)}>{membership.member_number || '—'}</strong></div>
          <div className="certificate-data-item"><span>MIEMBRO DESDE</span><strong data-testid={testIdFor('certificate-membership-date', exportMode)}>{formatMembershipDate(membershipDate(membership))}</strong></div>
          <div className="certificate-data-item"><span>FECHA DE EMISIÓN</span><strong data-testid={testIdFor('certificate-issue-date', exportMode)}>{formatMembershipDate(membership.certificate_issue_date)}</strong></div>
        </section>
        <section className="certificate-verification">
          <div className="certificate-qr-safe-zone">{qrSrc && <img src={qrSrc} alt="QR de verificación oficial" data-testid={testIdFor('certificate-qr', exportMode)} />}</div>
          <strong>VERIFICACIÓN DIGITAL</strong>
        </section>
      </div>
      <p className="certificate-mission">{INSTITUTION.mission}</p>
    </article>
  );
};