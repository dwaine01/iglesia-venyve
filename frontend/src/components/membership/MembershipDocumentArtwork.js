import React from 'react';

const NAVY = '#022e5a';
const BLUE = '#0798c8';
const GREEN = '#61b33b';
const WHITE = '#ffffff';
const OFF_WHITE = '#f7f9f8';

export const CardFrontArtwork = ({ id }) => (
  <svg id={`${id}-artwork`} data-vv-art="front" viewBox="0 0 260 540" preserveAspectRatio="none" aria-hidden="true">
    <path fill={OFF_WHITE} d="M112 0C25 124 17 377 122 540H260V0Z" />
    <path fill={GREEN} d="M145 0C51 138 52 382 158 540H189C80 367 81 156 179 0Z" />
    <path fill={WHITE} d="M165 0C71 144 74 379 180 540H199C94 367 96 158 190 0Z" />
    <path fill={BLUE} d="M181 0C91 147 92 383 199 540H229C122 361 119 166 211 0Z" />
    <path fill={WHITE} d="M199 0C113 156 116 375 217 540H229C132 367 133 171 218 0Z" />
    <path fill={NAVY} d="M216 0C131 154 137 384 235 540H260V0Z" />
    <path fill={BLUE} opacity=".16" d="M188 110h40v100h32v75h-32v155h-40V285h-45v-75h45Z" />
  </svg>
);

export const CardBackArtwork = ({ id }) => (
  <svg id={`${id}-artwork`} data-vv-art="back" viewBox="0 0 190 190" preserveAspectRatio="none" aria-hidden="true">
    <path fill={GREEN} d="M190 0v190H0C72 154 138 88 190 0Z" />
    <path fill={WHITE} d="M190 21v169H18c69-36 130-96 172-169Z" />
    <path fill={BLUE} d="M190 49v141H48c57-34 107-83 142-141Z" />
    <path fill={WHITE} d="M190 68v122H72c46-30 87-71 118-122Z" />
    <path fill={NAVY} d="M190 88v102H96c37-26 70-61 94-102Z" />
  </svg>
);

export const CertificateArtwork = ({ id }) => (
  <svg id={`${id}-artwork`} data-vv-art="certificate" viewBox="0 0 1100 850" preserveAspectRatio="none" aria-hidden="true">
    <rect x="14" y="14" width="1072" height="822" fill="none" stroke={NAVY} strokeWidth="4" />
    <rect x="21" y="21" width="1058" height="808" fill="none" stroke={BLUE} strokeWidth="1.5" />
    <path fill={NAVY} d="M-12-12h326C184 51 75 146-12 284Z" />
    <path fill="none" stroke={BLUE} strokeWidth="29" d="M282-12C164 47 67 148-15 279" />
    <path fill="none" stroke={WHITE} strokeWidth="8" d="M263-12C151 54 56 157-15 289" />
    <path fill="none" stroke={GREEN} strokeWidth="23" d="M245-12C139 60 49 165-15 300" />
    <path fill={NAVY} d="M-12 862h372C198 816 68 716-12 565Z" />
    <path fill="none" stroke={BLUE} strokeWidth="30" d="M-15 570C67 724 196 829 360 862" />
    <path fill="none" stroke={WHITE} strokeWidth="8" d="M-15 591C65 738 188 835 344 862" />
    <path fill="none" stroke={GREEN} strokeWidth="23" d="M-15 613C64 749 181 840 329 862" />
    <path fill={NAVY} d="M1112 862H794c143-49 246-151 318-308Z" />
    <path fill="none" stroke={BLUE} strokeWidth="30" d="M1115 559C1048 718 942 827 794 862" />
    <path fill="none" stroke={WHITE} strokeWidth="8" d="M1115 582C1047 733 944 834 812 862" />
    <path fill="none" stroke={GREEN} strokeWidth="23" d="M1115 607C1048 746 951 840 832 862" />
    <path fill={NAVY} opacity=".035" d="M995 70h52v130h82v60h-82v185h-52V260h-82v-60h82Z" />
    <path fill="none" stroke={WHITE} strokeWidth="3" d="M14 67c29 0 53-24 53-53m1019 53c-29 0-53-24-53-53M14 783c29 0 53 24 53 53m1019-53c-29 0-53 24-53 53" />
  </svg>
);