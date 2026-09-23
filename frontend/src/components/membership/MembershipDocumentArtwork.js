import React from 'react';

export const CardFrontArtwork = ({ id }) => (
  <svg id={`${id}-artwork`} data-vv-art="front" viewBox="0 0 260 540" preserveAspectRatio="none" aria-hidden="true">
    <path fill="var(--vv-off-white)" d="M112 0C25 124 17 377 122 540H260V0Z" />
    <path fill="var(--vv-green)" d="M145 0C51 138 52 382 158 540H189C80 367 81 156 179 0Z" />
    <path fill="var(--vv-white)" d="M165 0C71 144 74 379 180 540H199C94 367 96 158 190 0Z" />
    <path fill="var(--vv-blue)" d="M181 0C91 147 92 383 199 540H229C122 361 119 166 211 0Z" />
    <path fill="var(--vv-white)" d="M199 0C113 156 116 375 217 540H229C132 367 133 171 218 0Z" />
    <path fill="var(--vv-navy)" d="M216 0C131 154 137 384 235 540H260V0Z" />
    <path fill="var(--vv-blue)" opacity=".16" d="M218 215h42v70h-42v56h-35v-56h-40v-70h40v-57h35Z" />
  </svg>
);

export const CardBackArtwork = ({ id }) => (
  <svg id={`${id}-artwork`} data-vv-art="back" viewBox="0 0 190 190" preserveAspectRatio="none" aria-hidden="true">
    <path fill="var(--vv-green)" d="M190 0v190H0C72 154 138 88 190 0Z" />
    <path fill="var(--vv-white)" d="M190 21v169H18c69-36 130-96 172-169Z" />
    <path fill="var(--vv-blue)" d="M190 49v141H48c57-34 107-83 142-141Z" />
    <path fill="var(--vv-white)" d="M190 68v122H72c46-30 87-71 118-122Z" />
    <path fill="var(--vv-navy)" d="M190 88v102H96c37-26 70-61 94-102Z" />
  </svg>
);

export const CertificateArtwork = ({ id }) => (
  <svg id={`${id}-artwork`} data-vv-art="certificate" viewBox="0 0 1100 850" preserveAspectRatio="none" aria-hidden="true">
    <defs><clipPath id={`${id}-artwork-clip`}><rect x="22" y="22" width="1056" height="805" /></clipPath></defs>
    <rect x="14" y="14" width="1072" height="822" fill="none" stroke="var(--vv-navy)" strokeWidth="4" />
    <rect x="21" y="21" width="1058" height="808" fill="none" stroke="var(--vv-blue)" strokeWidth="1.5" />
    <g clipPath={`url(#${id}-artwork-clip)`}>
    <path fill="var(--vv-navy)" d="M22 22h270C176 72 84 145 22 255Z" />
    <path fill="none" stroke="var(--vv-blue)" strokeWidth="26" d="M257 22C159 70 78 148 22 241" />
    <path fill="none" stroke="var(--vv-white)" strokeWidth="7" d="M241 22C145 76 70 155 22 248" />
    <path fill="none" stroke="var(--vv-green)" strokeWidth="21" d="M226 22C137 80 65 162 22 256" />
    <path fill="var(--vv-navy)" d="M22 827h292C181 794 80 718 22 596Z" />
    <path fill="none" stroke="var(--vv-blue)" strokeWidth="27" d="M22 598C80 713 181 795 310 827" />
    <path fill="none" stroke="var(--vv-white)" strokeWidth="7" d="M22 615C80 724 176 801 297 827" />
    <path fill="none" stroke="var(--vv-green)" strokeWidth="21" d="M22 632C78 733 170 803 283 827" />
    <path fill="var(--vv-navy)" d="M1078 827H838c115-38 195-116 240-238Z" />
    <path fill="none" stroke="var(--vv-blue)" strokeWidth="27" d="M1078 591C1034 708 955 797 844 827" />
    <path fill="none" stroke="var(--vv-white)" strokeWidth="7" d="M1078 609C1032 720 957 801 856 827" />
    <path fill="none" stroke="var(--vv-green)" strokeWidth="21" d="M1078 628C1032 731 961 804 870 827" />
    <path fill="var(--vv-navy)" opacity=".035" d="M996 90h52v135h92v52h-92v138h-52V277h-91v-52h91Z" />
    </g>
    <path fill="none" stroke="var(--vv-white)" strokeWidth="3" d="M22 56c19 0 34-15 34-34m1022 34c-19 0-34-15-34-34M22 794c19 0 34 15 34 34m1022-34c-19 0-34 15-34 34" />
  </svg>
);