# Membership Documents — DESIGN LOCKED

`membership-documents-master.png` is the exact 1536 × 1024 visual master attached and approved by the user for:

- Membership card front — CR80 / 85.60 × 53.98 mm
- Membership card back — CR80 / 85.60 × 53.98 mm
- Membership certificate — US Letter landscape / 11 × 8.5 in / 279.4 × 215.9 mm

La implementación debe reconstruir el master, no reinterpretarlo: coordenadas físicas absolutas, logo con `object-fit: contain`, fotografía con `object-fit: cover`, QR únicamente en el reverso y SVGs vectoriales independientes para las geometrías institucionales.

Locked implementation files:

- `frontend/src/components/membership/MembershipDocumentArtwork.js`
- `frontend/src/components/membership/MembershipDocumentTokens.js`
- `frontend/src/components/membership/membership-documents.css`
- `frontend/src/components/membership/MembershipCardTemplates.js`
- `frontend/src/components/membership/MembershipCertificateTemplate.js`
- `frontend/src/components/membership/membershipPdf.js`

Any intentional visual change requires explicit user approval and regeneration of the golden snapshots.

Los goldens de implementación se crearán únicamente después de la aprobación visual final del usuario. Las firmas reales permanecen en configuración protegida y nunca se convierten en assets del repositorio.