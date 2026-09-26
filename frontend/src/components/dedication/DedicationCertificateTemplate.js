import React from 'react';

import './dedication-documents.css';
import { DedicationArtwork } from './DedicationArtwork';

const logoPath = '/assets/membership/church-logo.png';

const formatDate = (value) => {
  if (!value) return '—';
  try { return new Date(`${value}T00:00:00`).toLocaleDateString('es-ES', { day: '2-digit', month: 'long', year: 'numeric' }); }
  catch { return value; }
};

export const DedicationCertificateTemplate = ({ data, signatureSrc, qrSrc, exportMode = false }) => {
  const rootId = `vv-dedication-certificate-${exportMode ? 'export' : 'preview'}`;
  const child = data?.child || {};
  const dedication = data?.dedication || {};
  const certificate = data?.certificate || {};
  const parents = [dedication.father_name, dedication.mother_name].filter(Boolean).join(' y ') || '—';
  const witnesses = Array.isArray(dedication.witnesses) && dedication.witnesses.length ? dedication.witnesses.join(', ') : '—';
  return (
    <article id={rootId} data-vv-document="dedication-certificate" style={{ boxShadow: exportMode ? 'none' : undefined }} data-testid={`presentation-cert-root${exportMode ? '-export' : ''}`}>
      <DedicationArtwork id={rootId} />
      <img id={`${rootId}-logo`} data-vv-role="logo" src={logoPath} alt="Logo Ven y Ve" />
      <div id={`${rootId}-brand`} data-vv-role="brand"><strong>PRIMERA IGLESIA DEL NAZARENO</strong><b>VEN Y VE</b><span>Ministerio de Niños / Familia</span></div>
      <h1 id={`${rootId}-title`} data-vv-role="title">CERTIFICADO DE PRESENTACIÓN DE NIÑO/A</h1>
      <i id={`${rootId}-title-rule`} data-vv-role="title-rule" aria-hidden="true" />
      {dedication.dedication_verse && <p id={`${rootId}-verse`} data-vv-role="verse">“{dedication.dedication_verse}”</p>}
      <p id={`${rootId}-recognition`} data-vv-role="recognition">Presentamos con gozo a:</p>
      <h2 id={`${rootId}-name`} data-vv-role="child-name" data-testid="presentation-cert-child-name">{child.full_name}</h2>
      <p id={`${rootId}-birth-line`} data-vv-role="birth-line">Nacido(a) el {formatDate(child.fecha_nacimiento)}</p>
      <p id={`${rootId}-statement`} data-vv-role="statement">ha sido presentado(a) y dedicado(a) al Señor por sus padres, en obediencia y gratitud a Dios por el don de la vida, ante la congregación de la Primera Iglesia del Nazareno Ven y Ve.</p>
      <dl id={`${rootId}-facts`} data-vv-role="facts">
        <div><dt>PADRES</dt><dd data-testid="presentation-cert-parents">{parents}</dd></div>
        <div><dt>FECHA Y LUGAR</dt><dd>{formatDate(dedication.dedication_date)}{dedication.location ? ` · ${dedication.location}` : ''}</dd></div>
        <div><dt>TESTIGOS / PADRINOS</dt><dd data-testid="presentation-cert-witnesses">{witnesses}</dd></div>
      </dl>
      <section id={`${rootId}-signature`} data-vv-role="signature">
        <div>{signatureSrc && <img src={signatureSrc} alt="Firma autorizada" />}</div><i aria-hidden="true" />
        <strong data-testid="presentation-cert-officiant">MINISTRO OFICIANTE</strong>
        <small>{certificate.officiant_name || 'Pastor/a'}</small>
      </section>
      <section id={`${rootId}-verification`} data-vv-role="verification">
        <div data-vv-role="qr">{qrSrc && <img src={qrSrc} alt="QR de verificación oficial" data-testid="presentation-cert-qr" />}</div><strong>VERIFICACIÓN DIGITAL</strong>
      </section>
      <p id={`${rootId}-mission`} data-vv-role="mission"><i />CONOCIENDO A DIOS&nbsp;&nbsp; · &nbsp;&nbsp;HACIENDO FAMILIA&nbsp;&nbsp; · &nbsp;&nbsp;TRANSFORMANDO VIDAS<i /></p>
    </article>
  );
};
