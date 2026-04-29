// Cash Flow — Invoice detail slide-over
// Shows the full electronic invoice (factura electrónica) for a linked txn:
// vendor + customer header, line items, subtotals split by tax rate, IVA, tip, total.

const { useEffect: useEffectInv } = React;

function InvoiceDrawer({ txn, invoice, onClose }) {
  // Lock body-ish scroll while open (no-op outside artboard but cheap)
  useEffectInv(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose && onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!txn || !invoice) return null;
  const acc = ACCOUNT_BY_ID[txn.account];

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 50,
      display: 'flex', justifyContent: 'flex-end',
      background: 'color-mix(in oklch, var(--fg) 18%, transparent)',
      backdropFilter: 'blur(2px)',
    }}
    onClick={onClose}>
      <aside
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 560, maxWidth: '90%', height: '100%',
          background: 'var(--bg-elev)', borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--shadow-pop)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
        {/* Header */}
        <header style={{
          padding: '14px 20px',
          borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 12,
          background: 'var(--bg)',
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'var(--accent-soft)', color: 'var(--accent)',
            display: 'grid', placeItems: 'center', flex: 'none',
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2z"/>
              <line x1="9" y1="9" x2="15" y2="9"/>
              <line x1="9" y1="13" x2="15" y2="13"/>
              <line x1="9" y1="17" x2="13" y2="17"/>
            </svg>
          </div>
          <div style={{ flex: 1, lineHeight: 1.2, minWidth: 0 }}>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
              Factura electrónica
            </div>
            <div className="num" style={{ fontSize: 14.5, fontWeight: 600, letterSpacing: '-0.01em' }}>{invoice.number}</div>
          </div>
          <Pill tone="pos" dot>SRI · authorized</Pill>
          <button onClick={onClose} style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--fg-muted)', display: 'grid', placeItems: 'center',
          }}>{I.x}</button>
        </header>

        {/* Body — scrollable */}
        <div style={{ flex: 1, overflow: 'auto', padding: '18px 20px 100px' }}>
          {/* Vendor / customer */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10,
            marginBottom: 16,
          }}>
            <Block label="Vendor">
              <div style={{ fontSize: 13.5, fontWeight: 600, lineHeight: 1.3 }}>{invoice.vendor.tradeName}</div>
              <div style={{ fontSize: 11.5, color: 'var(--fg-muted)' }}>{invoice.vendor.name}</div>
              <div className="num" style={{ fontSize: 11.5, color: 'var(--fg-faint)', marginTop: 4 }}>RUC · {invoice.vendor.taxId}</div>
              <div style={{ fontSize: 11.5, color: 'var(--fg-faint)', marginTop: 2 }}>{invoice.vendor.address}</div>
            </Block>
            <Block label="Customer">
              <div style={{ fontSize: 13.5, fontWeight: 600, lineHeight: 1.3 }}>{invoice.customer.name}</div>
              <div className="num" style={{ fontSize: 11.5, color: 'var(--fg-faint)' }}>CI · {invoice.customer.taxId}</div>
              <div style={{ fontSize: 11.5, color: 'var(--fg-faint)' }}>{invoice.customer.email}</div>
              <div style={{ fontSize: 11.5, color: 'var(--fg-muted)', marginTop: 6 }}>
                Issued <span className="num">{invoice.issuedAt}</span>
              </div>
            </Block>
          </div>

          {/* Linked transaction summary */}
          <div style={{
            border: '1px solid var(--border)', borderRadius: 12,
            background: 'var(--bg-sunken)',
            padding: '10px 14px', marginBottom: 18,
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <CatSwatch cat={txn.category} size={26}/>
            <div style={{ flex: 1, lineHeight: 1.3, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 550 }}>{txn.desc}</div>
              <div style={{ fontSize: 11.5, color: 'var(--fg-faint)', display: 'flex', gap: 8 }}>
                <AccountChip account={acc}/>
                <span>·</span>
                <span className="num">{fmtDateLong(txn.date_payed)}</span>
              </div>
            </div>
            <div className="num" style={{ fontSize: 14.5, fontWeight: 600, color: txn.amount > 0 ? 'var(--pos)' : 'var(--fg)' }}>
              {fmtMoney(txn.amount)}
            </div>
          </div>

          {/* Line items */}
          <SectionLabel>Line items <span style={{ color: 'var(--fg-faint)', fontWeight: 500 }}>· {invoice.items.length}</span></SectionLabel>
          <div style={{
            border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden',
            background: 'var(--bg-elev)',
          }}>
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 50px 80px 80px',
              gap: 10, padding: '8px 14px',
              fontSize: 10.5, fontWeight: 600, color: 'var(--fg-faint)',
              letterSpacing: '0.05em', textTransform: 'uppercase',
              background: 'var(--bg-sunken)', borderBottom: '1px solid var(--border)',
            }}>
              <div>Description</div>
              <div style={{ textAlign: 'right' }}>Qty</div>
              <div style={{ textAlign: 'right' }}>Unit</div>
              <div style={{ textAlign: 'right' }}>Total</div>
            </div>
            {invoice.items.map((it, i) => {
              const lineTotal = it.qty * it.price - (it.discount || 0);
              return (
                <div key={i} style={{
                  display: 'grid', gridTemplateColumns: '1fr 50px 80px 80px',
                  gap: 10, padding: '10px 14px',
                  borderTop: i === 0 ? 'none' : '1px solid var(--border)',
                  alignItems: 'baseline',
                }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.3 }}>{it.name}</div>
                    <div className="num" style={{ fontSize: 10.5, color: 'var(--fg-faint)', marginTop: 1 }}>
                      SKU · {it.sku}
                      {it.tax > 0 ? <span style={{ marginLeft: 6 }}>· IVA 12%</span> : <span style={{ marginLeft: 6 }}>· IVA 0%</span>}
                      {it.discount ? <span style={{ marginLeft: 6, color: 'var(--neg)' }}>· −{fmtMoney(it.discount)} disc</span> : null}
                    </div>
                  </div>
                  <div className="num" style={{ textAlign: 'right', fontSize: 12.5, color: 'var(--fg-muted)' }}>
                    {Number.isInteger(it.qty) ? it.qty : it.qty.toFixed(2)}
                  </div>
                  <div className="num" style={{ textAlign: 'right', fontSize: 12.5, color: 'var(--fg-muted)' }}>
                    ${it.price.toFixed(2)}
                  </div>
                  <div className="num" style={{ textAlign: 'right', fontSize: 13, fontWeight: 600 }}>
                    ${lineTotal.toFixed(2)}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Totals */}
          <SectionLabel style={{ marginTop: 18 }}>Totals</SectionLabel>
          <div style={{
            border: '1px solid var(--border)', borderRadius: 12,
            background: 'var(--bg-elev)', padding: '6px 14px',
          }}>
            <Total k="Subtotal IVA 0%"  v={`$${invoice.subtotal0.toFixed(2)}`}/>
            <Total k="Subtotal IVA 12%" v={`$${invoice.subtotal12.toFixed(2)}`}/>
            {invoice.discount ? <Total k="Discount" v={`−$${invoice.discount.toFixed(2)}`} tone="neg"/> : null}
            <Total k="IVA 12%" v={`$${invoice.iva.toFixed(2)}`}/>
            {invoice.tip ? <Total k="Service / propina (10%)" v={`$${invoice.tip.toFixed(2)}`}/> : null}
            <div style={{ height: 1, background: 'var(--border)', margin: '6px 0' }}/>
            <Total k="Total" v={`$${invoice.total.toFixed(2)}`} big/>
          </div>

          {/* Payment + auth */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 14,
          }}>
            <Block label="Payment">
              <div style={{ fontSize: 12.5, fontWeight: 550 }}>{invoice.paymentMethod}</div>
              <div style={{ fontSize: 11.5, color: 'var(--fg-faint)', marginTop: 2 }}>Charged on {fmtDateLong(txn.date_payed)}</div>
            </Block>
            <Block label="Authorization">
              <div className="num" style={{ fontSize: 11.5, color: 'var(--fg-muted)', wordBreak: 'break-all', lineHeight: 1.4 }}>{invoice.auth}</div>
              <div style={{ fontSize: 11, color: 'var(--fg-faint)', marginTop: 2 }}>SRI · received via Gmail</div>
            </Block>
          </div>
        </div>

        {/* Footer actions */}
        <footer style={{
          padding: '12px 20px',
          borderTop: '1px solid var(--border)',
          background: 'var(--bg)',
          display: 'flex', alignItems: 'center', gap: 8,
          position: 'absolute', bottom: 0, left: 0, right: 0,
        }}>
          <Btn kind="ghost" size="sm" icon={I.receipt}>Open original</Btn>
          <span style={{ flex: 1 }}/>
          <Btn kind="soft" size="sm">Download XML</Btn>
          <Btn kind="primary" size="sm">Download PDF</Btn>
        </footer>
      </aside>
    </div>
  );
}

function Block({ label, children }) {
  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 12,
      padding: '10px 12px', background: 'var(--bg-elev)',
    }}>
      <div style={{
        fontSize: 10.5, fontWeight: 600, color: 'var(--fg-faint)',
        letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6,
      }}>{label}</div>
      {children}
    </div>
  );
}

function SectionLabel({ children, style }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, color: 'var(--fg-muted)',
      letterSpacing: '0.06em', textTransform: 'uppercase',
      marginBottom: 8,
      ...style,
    }}>{children}</div>
  );
}

function Total({ k, v, big = false, tone = 'neutral' }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'baseline',
      padding: big ? '8px 0' : '4px 0',
    }}>
      <div style={{
        flex: 1, fontSize: big ? 14 : 12.5,
        fontWeight: big ? 600 : 500,
        color: big ? 'var(--fg)' : 'var(--fg-muted)',
      }}>{k}</div>
      <div className="num" style={{
        fontSize: big ? 18 : 13,
        fontWeight: big ? 700 : 600,
        letterSpacing: big ? '-0.02em' : '-0.01em',
        color: tone === 'neg' ? 'var(--neg)' : 'var(--fg)',
      }}>{v}</div>
    </div>
  );
}

Object.assign(window, { InvoiceDrawer });
