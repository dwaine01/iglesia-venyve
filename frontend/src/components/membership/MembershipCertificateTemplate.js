import React from 'react';

import './membership-documents.css';
import { formatMembershipDate, membershipDate, nameLengthClass } from './membershipDocumentUtils';

const logoPath = '/assets/membership/church-logo.png';

export const MembershipCertificateTemplate = ({ data, signatureSrc, qrSrc, exportMode = false }) => {
  const person = data?.person || {};
  const membership = data?.membership || {};
  const certificate = data?.certificate || {};
  return (
    <article className={`membership-certificate ${exportMode ? 'document-export' : ''}`} data-testid="membership-certificate-template">
      <div className="certificate-border certificate-border-outer" aria-hidden="true" />
      <div className="certificate-border certificate-border-inner" aria-hidden="true" />
      <div className="certificate-corner certificate-corner-tl" aria-hidden="true" />
      <div className="certificate-corner certificate-corner-tr" aria-hidden="true" />
      <div className="certificate-corner certificate-corner-bl" aria-hidden="true" />
      <div className="certificate-corner certificate-corner-br" aria-hidden="true" />
      <img src={logoPath} alt="" className="certificate-watermark" aria-hidden="true" />
      <header className="certificate-header">
        <img src={logoPath} alt="Casa de Oración Ven y Ve" />
        <p>CASA DE ORACIÓN VEN Y VE</p>
        <span>RECONOCIMIENTO OFICIAL DE MEMBRESÍA</span>
      </header>
      <main className="certificate-main">
        <h1>CERTIFICADO DE MEMBRESÍA</h1>
        <div className="certificate-title-rule"><i /><span>✦</span><i /></div>
        <p className="certificate-preamble">Se certifica con gozo y gratitud que</p>
        <h2 className={nameLengthClass(person.full_name)} data-testid="certificate-member-name">{person.full_name}</h2>
        <p className="certificate-statement">ha sido reconocido(a) formalmente como <strong>Miembro Activo</strong> de esta congregación, afirmando su comunión, fe y servicio como parte del cuerpo de Cristo.</p>
        <p className="certificate-verse">“Así nosotros, siendo muchos, somos un cuerpo en Cristo, y todos miembros los unos de los otros.” <strong>Romanos 12:5</strong></p>
      </main>
      <footer className="certificate-footer">
        <section className="certificate-signature-block">
          <div className="certificate-signature-space">{signatureSrc && <img src={signatureSrc} alt="Firma autorizada" data-testid="certificate-signature-image" />}</div>
          <strong>{certificate.authorized_signer_name || 'Pastora Principal'}</strong>
          <span>{certificate.authorized_signer_title || 'Pastora Principal'}</span>
        </section>
        <section className="certificate-official-data">
          <div><span>Nº OFICIAL DE MIEMBRO</span><strong data-testid="certificate-member-number">{membership.member_number || '—'}</strong></div>
          <div><span>FECHA DE MEMBRESÍA</span><strong data-testid="certificate-membership-date">{formatMembershipDate(membershipDate(membership))}</strong></div>
          <div><span>FECHA DE EMISIÓN</span><strong data-testid="certificate-issue-date">{formatMembershipDate(membership.certificate_issue_date)}</strong></div>
        </section>
        <section className="certificate-verification">
          <div className="certificate-qr-safe-zone">{qrSrc && <img src={qrSrc} alt="QR de verificación oficial" data-testid="certificate-qr" />}</div>
          <div><strong>VERIFICACIÓN OFICIAL</strong><span>Autenticidad digital</span></div>
        </section>
      </footer>
    </article>
  );
};