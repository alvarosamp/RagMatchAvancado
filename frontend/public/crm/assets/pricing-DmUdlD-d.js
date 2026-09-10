import{p as l,j as n,b as u,L as s}from"./index-DkjxmE9k.js";/**
 * @license lucide-react v0.462.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const x=l("DollarSign",[["line",{x1:"12",x2:"12",y1:"2",y2:"22",key:"7eqyqh"}],["path",{d:"M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",key:"1b0p4s"}]]);/**
 * @license lucide-react v0.462.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const f=l("Gavel",[["path",{d:"m14.5 12.5-8 8a2.119 2.119 0 1 1-3-3l8-8",key:"15492f"}],["path",{d:"m16 16 6-6",key:"vzrcl6"}],["path",{d:"m8 8 6-6",key:"18bi4p"}],["path",{d:"m9 7 8 8",key:"5jnvq1"}],["path",{d:"m21 11-8-8",key:"z4y7zo"}]]);/**
 * @license lucide-react v0.462.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const i=l("Inbox",[["polyline",{points:"22 12 16 12 14 15 10 15 8 12 2 12",key:"o97t9d"}],["path",{d:"M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",key:"oot6mr"}]]);/**
 * @license lucide-react v0.462.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const y=l("MapPin",[["path",{d:"M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0",key:"1r0f0z"}],["circle",{cx:"12",cy:"10",r:"3",key:"ilqhr7"}]]);function h({title:e,description:r,icon:t=i,compact:a=!1,className:c}){return n.jsx("div",{className:u("grid place-items-center rounded-md border border-dashed bg-muted/20 px-4 text-center text-muted-foreground",a?"py-4":"py-8",c),children:n.jsxs("div",{className:"max-w-sm space-y-2",children:[n.jsx(t,{className:u("mx-auto text-muted-foreground/55",a?"h-4 w-4":"h-6 w-6")}),n.jsx("p",{className:u("font-medium text-foreground",a?"text-xs":"text-sm"),children:e}),r&&n.jsx("p",{className:"text-xs text-muted-foreground",children:r})]})})}function b({label:e="Carregando dados",className:r}){return n.jsx("div",{className:u("grid place-items-center rounded-md border bg-card/70 px-4 py-10 text-center shadow-[var(--shadow-card)]",r),children:n.jsxs("div",{className:"space-y-2 text-sm text-muted-foreground",children:[n.jsx(s,{className:"mx-auto h-5 w-5 animate-spin text-primary"}),n.jsx("p",{children:e})]})})}function o(e){return e.reference_total_price!=null?Number(e.reference_total_price):e.reference_price!=null&&e.quantity!=null?Number(e.reference_price)*Number(e.quantity):null}function N(e){const r=e.map(o).filter(t=>t!=null);return r.length?r.reduce((t,a)=>t+a,0):null}function _(e,r){return e!=null?Number(e):r==null?null:Number(r)}function d(e){const r=e.catalog_products;return(r==null?void 0:r.min_price)!=null?Number(r.min_price):null}function m(e){return e.minimum_unit_price!=null?Number(e.minimum_unit_price):d(e)??(e.reference_price==null?null:Number(e.reference_price))}function g(e){const r=m(e);return r==null||e.quantity==null?null:r*Number(e.quantity)}export{x as D,h as E,f as G,b as L,y as M,m as a,_ as c,d as l,g as m,o as r,N as s};
