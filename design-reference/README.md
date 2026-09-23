# Membership Documents — DESIGN LOCKED

`membership-documents-master.png` is the approved visual master accepted by the user for:

- Membership card front — CR80 / 85.60 × 53.98 mm
- Membership card back — CR80 / 85.60 × 53.98 mm
- Membership certificate — US Letter landscape / 11 × 8.5 in / 279.4 × 215.9 mm

The master uses the exact logo colors (#01A1C8 and #6ECE3C), white paper, Grid/Flexbox structure and isolated physical dimensions. Dynamic fields remain HTML/CSS content: member photo, name, member number, dates, status, configured signature, and verification QR.

Locked implementation files:

- `frontend/src/components/membership/membership-identity-documents.css`
- `frontend/src/components/membership/MembershipCardTemplates.js`
- `frontend/src/components/membership/MembershipCertificateTemplate.js`
- `frontend/src/components/membership/membershipPdf.js`

Any intentional visual change requires explicit user approval and regeneration of the golden snapshots.

`goldens/` contains the certified Iteration 52 PDF render baselines. The signature shown is an abstract QA placeholder; real signatures remain dynamic protected configuration and are never repository assets.