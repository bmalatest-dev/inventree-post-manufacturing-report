export function renderPanel(ctx) {
  const React = globalThis.React;
  if (!React) return null;
  const e = React.createElement;
  return e('div', {style:{padding:'12px'}},
    e('p', null, 'Create a PCBA, Mechanical, or Final Product post-manufacturing report for this Build Order.'),
    e('p', null, 'V0.1.0 discovers BOM / candidate PO data and stores draft/finalized snapshots on the BO.'),
    e('a', {href: ctx.report_url, style:{fontWeight:600}}, 'Open Post-Manufacturing Report')
  );
}
