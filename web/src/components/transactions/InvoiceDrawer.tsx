import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { TimelineTransaction, Invoice } from '../../api/types';
import { fmtMoney, fmtDateLong } from '../../utils/format';
import CatSwatch from '../primitives/CatSwatch';
import Pill from '../primitives/Pill';

interface Props {
  txn: TimelineTransaction;
  onClose: () => void;
}

export default function InvoiceDrawer({ txn, onClose }: Props) {
  const { data: invoice, isLoading } = useQuery<Invoice>({
    queryKey: ['invoice-by-txn', txn.id],
    queryFn: () => api.invoiceByTransaction(txn.id),
    enabled: txn.has_invoice,
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        display: 'flex', justifyContent: 'flex-end',
        background: 'color-mix(in oklch, var(--fg) 18%, transparent)',
        backdropFilter: 'blur(2px)',
      }}
      onClick={onClose}
    >
      <aside
        onClick={e => e.stopPropagation()}
        style={{
          width: 560, maxWidth: '90%', height: '100%',
          background: 'var(--bg-elev)', borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--shadow-pop)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        {/* Header */}
        <header style={{
          padding: '14px 20px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 12, background: 'var(--bg)',
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'var(--accent-soft)', color: 'var(--accent)',
            display: 'grid', placeItems: 'center', flexShrink: 0,
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2z"/>
              <line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="13" y2="17"/>
            </svg>
          </div>
          <div style={{ flex: 1, lineHeight: 1.2, minWidth: 0 }}>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
              Factura electr&oacute;nica
            </div>
            <div className="num" style={{ fontSize: 14.5, fontWeight: 600, letterSpacing: '-0.01em' }}>
              {invoice?.invoice_number ?? '...'}
            </div>
          </div>
          {invoice && <Pill tone="pos" dot>SRI &middot; authorized</Pill>}
          <button onClick={onClose} style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--fg-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer',
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </header>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '18px 20px 100px' }}>
          {isLoading && <div style={{ padding: 20, color: 'var(--fg-muted)' }}>Loading...</div>}
          {invoice && <InvoiceBody txn={txn} invoice={invoice} />}
        </div>
      </aside>
    </div>
  );
}

function InvoiceBody({ txn, invoice }: { txn: TimelineTransaction; invoice: Invoice }) {
  const lines = invoice.lines || [];
  const taxes = invoice.taxes || [];

  const subtotal12 = taxes.filter(t => t.rate_pct > 0).reduce((s, t) => s + t.base_imponible, 0);
  const subtotal0 = invoice.subtotal_sin_impuesto - subtotal12;
  const ivaTotal = taxes.filter(t => t.rate_pct > 0).reduce((s, t) => s + t.tax_value, 0);

  return (
    <>
      {/* Vendor / Customer */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
        <Block label="Vendor">
          <div style={{ fontSize: 13.5, fontWeight: 600, lineHeight: 1.3 }}>
            {invoice.vendor_trade_name || invoice.vendor}
          </div>
          {invoice.vendor_trade_name && (
            <div style={{ fontSize: 11.5, color: 'var(--fg-muted)' }}>{invoice.vendor}</div>
          )}
          <div className="num" style={{ fontSize: 11.5, color: 'var(--fg-faint)', marginTop: 4 }}>
            RUC &middot; {invoice.ruc}
          </div>
          {invoice.store_address && (
            <div style={{ fontSize: 11.5, color: 'var(--fg-faint)', marginTop: 2 }}>{invoice.store_address}</div>
          )}
        </Block>
        <Block label="Details">
          <div style={{ fontSize: 12.5, fontWeight: 550 }}>
            {invoice.doc_type === 'nota_credito' ? 'Nota de crédito' : 'Factura'}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--fg-faint)', marginTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span className="num">Bought {fmtDateLong(txn.date_created)}</span>
            {txn.date_created !== txn.date_payed && (
              <span className="num">Pays {fmtDateLong(txn.date_payed)}</span>
            )}
            <span className="num">Issued {invoice.issue_date}</span>
          </div>
        </Block>
      </div>

      {/* Linked transaction */}
      <div style={{
        border: '1px solid var(--border)', borderRadius: 12,
        background: 'var(--bg-sunken)', padding: '10px 14px', marginBottom: 18,
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <CatSwatch cat={txn.category} size={26} />
        <div style={{ flex: 1, lineHeight: 1.3, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 550 }}>{txn.description}</div>
          <div style={{ fontSize: 11.5, color: 'var(--fg-faint)', display: 'flex', gap: 8 }}>
            <span>{txn.account}</span>
            <span>&middot;</span>
            <span className="num">pays {fmtDateLong(txn.date_payed)}</span>
          </div>
        </div>
        <div className="num" style={{
          fontSize: 14.5, fontWeight: 600,
          color: txn.amount > 0 ? 'var(--pos)' : 'var(--fg)',
        }}>
          {fmtMoney(txn.amount)}
        </div>
      </div>

      {/* Line items */}
      {lines.length > 0 && (
        <>
          <SectionLabel>Line items &middot; {lines.length}</SectionLabel>
          <div style={{
            border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden',
            background: 'var(--bg-elev)', marginBottom: 18,
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
            {lines.map((it, i) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '1fr 50px 80px 80px',
                gap: 10, padding: '10px 14px',
                borderTop: i === 0 ? 'none' : '1px solid var(--border)',
                alignItems: 'baseline',
              }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.3 }}>{it.description}</div>
                  <div className="num" style={{ fontSize: 10.5, color: 'var(--fg-faint)', marginTop: 1 }}>
                    {it.sku && <span>SKU &middot; {it.sku}</span>}
                    {it.tax_rate != null && it.tax_rate > 0
                      ? <span style={{ marginLeft: 6 }}>&middot; IVA {it.tax_rate}%</span>
                      : <span style={{ marginLeft: 6 }}>&middot; IVA 0%</span>
                    }
                    {it.discount > 0 && (
                      <span style={{ marginLeft: 6, color: 'var(--neg)' }}>&middot; &minus;{fmtMoney(it.discount)} disc</span>
                    )}
                  </div>
                </div>
                <div className="num" style={{ textAlign: 'right', fontSize: 12.5, color: 'var(--fg-muted)' }}>
                  {Number.isInteger(it.quantity) ? it.quantity : it.quantity.toFixed(2)}
                </div>
                <div className="num" style={{ textAlign: 'right', fontSize: 12.5, color: 'var(--fg-muted)' }}>
                  ${it.unit_price.toFixed(2)}
                </div>
                <div className="num" style={{ textAlign: 'right', fontSize: 13, fontWeight: 600 }}>
                  ${it.line_total.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Totals */}
      <SectionLabel>Totals</SectionLabel>
      <div style={{
        border: '1px solid var(--border)', borderRadius: 12,
        background: 'var(--bg-elev)', padding: '6px 14px', marginBottom: 14,
      }}>
        {subtotal0 > 0 && <TotalRow k="Subtotal IVA 0%" v={`$${subtotal0.toFixed(2)}`} />}
        {subtotal12 > 0 && <TotalRow k="Subtotal IVA 12%" v={`$${subtotal12.toFixed(2)}`} />}
        {invoice.total_descuento > 0 && <TotalRow k="Discount" v={`−$${invoice.total_descuento.toFixed(2)}`} tone="neg" />}
        {ivaTotal > 0 && <TotalRow k="IVA 12%" v={`$${ivaTotal.toFixed(2)}`} />}
        {invoice.propina > 0 && <TotalRow k="Propina (10%)" v={`$${invoice.propina.toFixed(2)}`} />}
        <div style={{ height: 1, background: 'var(--border)', margin: '6px 0' }} />
        <TotalRow k="Total" v={`$${invoice.total.toFixed(2)}`} big />
      </div>

      {/* Payment */}
      {invoice.forma_pago != null && (
        <Block label="Payment">
          <div style={{ fontSize: 12.5, fontWeight: 550 }}>
            {FORMA_PAGO[invoice.forma_pago] || `Code ${invoice.forma_pago}`}
          </div>
        </Block>
      )}
    </>
  );
}

const FORMA_PAGO: Record<number, string> = {
  1: 'Sin utilización del sistema financiero',
  15: 'Compensación de deudas',
  16: 'Tarjeta de débito',
  17: 'Dinero electrónico',
  18: 'Tarjeta prepago',
  19: 'Tarjeta de crédito',
  20: 'Otros con utilización del sistema financiero',
  21: 'Endoso de títulos',
};

function Block({ label, children }: { label: string; children: React.ReactNode }) {
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

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, color: 'var(--fg-muted)',
      letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8,
    }}>{children}</div>
  );
}

function TotalRow({ k, v, big, tone }: { k: string; v: string; big?: boolean; tone?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', padding: big ? '8px 0' : '4px 0' }}>
      <div style={{
        flex: 1, fontSize: big ? 14 : 12.5,
        fontWeight: big ? 600 : 500,
        color: big ? 'var(--fg)' : 'var(--fg-muted)',
      }}>{k}</div>
      <div className="num" style={{
        fontSize: big ? 18 : 13, fontWeight: big ? 700 : 600,
        letterSpacing: big ? '-0.02em' : '-0.01em',
        color: tone === 'neg' ? 'var(--neg)' : 'var(--fg)',
      }}>{v}</div>
    </div>
  );
}
