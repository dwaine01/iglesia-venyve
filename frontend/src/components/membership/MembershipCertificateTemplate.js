import React from 'react';

import './membership-documents.css';
import { formatMembershipDate, membershipDate, nameLengthClass } from './membershipDocumentUtils';

const logoPath = '/assets/membership/church-logo.png';

export const MembershipCertificateTemplate = ({ data, signatureSrc, qrSrc, exportMode = false }) => {
  const person = data?.person || {};
  const membership = data?.membership || {};
  const certificate = data?.certificate || {};
  const organization = certificate.organization_name || 'Casa de Oración Ven y Ve';
  return (
    <article className={`membership-certificate ${exportMode ? 'document-export' : ''}`} data-testid="membership-certificate-template">
      <div className="certificate-frame" aria-hidden="true" />
      <div className="certificate-frame-accent" aria-hidden="true" />
      <header className="certificate-header">
        <img src={logoPath} alt="Casa de Oración Ven y Ve" />
        <div><span>CASA DE ORACIÓN</span><strong>VEN Y VE</strong></div>
      </header>
      <main className="certificate-main">
        <p className="certificate-eyebrow">RECONOCIMIENTO INSTITUCIONAL</p>
        <h1 aria-label="CERTIFICADO DE MEMBRESÍA"><span>CERTIFICADO</span><span>DE MEMBRESÍA</span></h1>
        <div className="certificate-rule" aria-hidden="true" />
        <p className="certificate-preamble">Se certifica que</p>
        <h2 className={nameLengthClass(person.full_name)} data-testid="certificate-member-name">{person.full_name}</h2>
        <p className="certificate-statement">es miembro activo de {organization}, reconocido(a) dentro de nuestra comunidad de fe, comunión y servicio.</p>
      </main>
      <footer className="certificate-footer">
        <section className="certificate-signature-block">
          <div className="certificate-signature-space">{signatureSrc && <img src={signatureSrc} alt="Firma autorizada" data-testid="certificate-signature-image" />}</div>
          <strong>{certificate.authorized_signer_name || 'Pastora Principal'}</strong>
          <span>{certificate.authorized_signer_title || 'Pastora Principal'}</span>
        </section>
        <section className="certificate-official-data">
          <div><span>NÚMERO OFICIAL</span><strong data-testid="certificate-member-number">{membership.member_number || '—'}</strong></div>
          <div><span>MIEMBRO DESDE</span><strong data-testid="certificate-membership-date">{formatMembershipDate(membershipDate(membership))}</strong></div>
          <div><span>FECHA DE EMISIÓN</span><strong data-testid="certificate-issue-date">{formatMembershipDate(membership.certificate_issue_date)}</strong></div>
        </section>
        <section className="certificate-verification">
          <div className="certificate-qr-safe-zone">{qrSrc && <img src={qrSrc} alt="QR de verificación oficial" data-testid="certificate-qr" />}</div>
          <strong>VERIFICACIÓN DE MEMBRESÍA</strong>
        </section>
      </footer>
    </article>
  );
};