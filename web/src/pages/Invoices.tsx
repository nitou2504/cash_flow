import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Invoice, Consumo } from '../api/types';
import { fmtMoney, fmtDate, fmtDateLong } from '../utils/format';
import Segmented from '../components/primitives/Segmented';
import { FORMA_PAGO } from '../components/transactions/InvoiceDrawer';

export default function Invoices() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState('card');
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const cardOnly = filter === 'card';
  const { data: invoices, isLoading } = useQuery<Invoice[]>({
    queryKey: ['unmatched-invoices', cardOnly],
    queryFn: () => api.unmatchedInvoices(cardOnly),
    refetchOnMount: 'always',
    staleTime: 0,
  });

  const selected = invoices?.find(i => i.id === selectedId) || null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16,
        padding: '14px 28px', borderBottom: '1px solid var(--border)',
        background: 'color-mix(in oklch, var(--bg) 92%, transparent)',
        backdropFilter: 'blur(8px)', position: 'sticky', top: 0, zIndex: 5, minHeight: 60,
      }}>
        <div style={{ flex: 1, lineHeight: 1.2 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.015em' }}>Unmatched Invoices</span>
            {invoices && invoices.length > 0 && (
              <span style={{
                fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10,
                background: 'var(--warn-soft)', color: 'var(--warn)',
              }}>{invoices.length}</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            Email invoices with no card transaction linked
          </div>
        </div>
        <Segmented value={filter} onChange={v => { setFilter(v); setSelectedId(null); }} size="sm" options={[
          { value: 'card', label: 'Card-paid' },
          { value: 'all', label: 'All' },
        ]} />
      </div>

      {/* Split view */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left: invoice list */}
        <div style={{ flex: 1, overflow: 'auto', minWidth: 0 }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: '78px 1fr 170px 90px',
            gap: 8, padding: '8px 20px', background: 'var(--bg-sunken)',
            borderBottom: '1px solid var(--border)', fontSize: 11, fontWeight: 600,
            color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase',
          }}>
            <div>Date</div>
            <div>Vendor</div>
            <div>Payment</div>
            <div style={{ textAlign: 'right' }}>Total</div>
          </div>

          {isLoading && <div style={{ padding: 28, color: 'var(--fg-muted)' }}>Loading...</div>}

          {invoices?.map(inv => (
            <div
              key={inv.id}
              onClick={() => setSelectedId(inv.id)}
              style={{
                display: 'grid',
                gridTemplateColumns: '78px 1fr 170px 90px',
                gap: 8, padding: '10px 20px',
                background: selectedId === inv.id ? 'var(--bg-hover)' : 'transparent',
                borderTop: '1px solid var(--border)',
                cursor: 'pointer', alignItems: 'center', fontSize: 13,
              }}
            >
              <div className="num" style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{fmtDate(inv.issue_date)}</div>
              <div style={{ minWidth: 0, lineHeight: 1.3 }}>
                <div style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {inv.vendor_trade_name || inv.vendor}
                </div>
                <div style={{ fontSize: 11, color: 'var(--fg-faint)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {inv.store_address || inv.invoice_number}
                </div>
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--fg-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {inv.forma_pago != null ? (FORMA_PAGO[inv.forma_pago] || `Code ${inv.forma_pago}`) : '—'}
              </div>
              <div className="num" style={{ textAlign: 'right', fontWeight: 600 }}>${inv.total.toFixed(2)}</div>
            </div>
          ))}

          {invoices && invoices.length === 0 && !isLoading && (
            <div style={{
              padding: '80px 40px', textAlign: 'center',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
            }}>
              <div style={{
                width: 56, height: 56, borderRadius: '50%',
                background: 'var(--pos-soft)', color: 'var(--pos)',
                display: 'grid', placeItems: 'center', fontSize: 28,
              }}>&#10003;</div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>All matched</div>
              <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>Every invoice is linked to a card transaction</div>
            </div>
          )}
        </div>

        {/* Right: detail + candidates */}
        {selected && (
          <DetailPanel
            invoice={selected}
            onLinked={() => {
              queryClient.invalidateQueries({ queryKey: ['unmatched-invoices'] });
              queryClient.invalidateQueries({ queryKey: ['invoice-candidates'] });
              queryClient.invalidateQueries({ queryKey: ['review'] });
              setSelectedId(null);
            }}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>
    </div>
  );
}

/* ── Detail Panel ── */

function DetailPanel({ invoice, onLinked, onClose }: {
  invoice: Invoice;
  onLinked: () => void;
  onClose: () => void;
}) {
  const [windowDays, setWindowDays] = useState(7);

  const { data: candidates, isLoading } = useQuery<Consumo[]>({
    queryKey: ['invoice-candidates', invoice.id, windowDays],
    queryFn: () => api.invoiceCandidates(invoice.id, windowDays),
    staleTime: 0,
  });

  const linkMut = useMutation({
    mutationFn: (consumoId: number) => api.linkInvoice(invoice.id, consumoId),
    onSuccess: onLinked,
  });

  const lines = invoice.lines || [];

  return (
    <div style={{
      width: 460, borderLeft: '1px solid var(--border)',
      overflow: 'auto', background: 'var(--bg-elev)',
      display: 'flex', flexDirection: 'column',
    }}>
      <header style={{
        padding: '14px 18px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10, background: 'var(--bg)',
        flexShrink: 0,
      }}>
        <div style={{ flex: 1, lineHeight: 1.2, minWidth: 0 }}>
          <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
            Factura
          </div>
          <div className="num" style={{ fontSize: 13, fontWeight: 600 }}>{invoice.invoice_number}</div>
        </div>
        <button onClick={onClose} style={{
          width: 28, height: 28, borderRadius: 7,
          background: 'transparent', border: '1px solid var(--border)',
          color: 'var(--fg-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer',
        }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </header>

      <div style={{ flex: 1, overflow: 'auto', padding: '18px 18px 60px' }}>
        {/* Invoice summary */}
        <div style={{
          border: '1px solid var(--border)', borderRadius: 12,
          background: 'var(--bg-sunken)', padding: '12px 14px', marginBottom: 16,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{invoice.vendor_trade_name || invoice.vendor}</div>
          <div style={{ fontSize: 11.5, color: 'var(--fg-muted)', marginTop: 2 }}>
            {fmtDateLong(invoice.issue_date)}
            {invoice.store_address && <> &middot; {invoice.store_address}</>}
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', marginTop: 8 }}>
            <span style={{ flex: 1, fontSize: 12, color: 'var(--fg-muted)' }}>
              {invoice.forma_pago != null ? (FORMA_PAGO[invoice.forma_pago] || `Code ${invoice.forma_pago}`) : 'Payment unknown'}
            </span>
            <span className="num" style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em' }}>
              ${invoice.total.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Line items (compact) */}
        {lines.length > 0 && (
          <details style={{ marginBottom: 18 }}>
            <summary style={{
              fontSize: 11, fontWeight: 600, color: 'var(--fg-muted)',
              letterSpacing: '0.06em', textTransform: 'uppercase',
              cursor: 'pointer', marginBottom: 8,
            }}>
              Line items &middot; {lines.length}
            </summary>
            <div style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
              {lines.map((it, i) => (
                <div key={i} style={{
                  display: 'flex', gap: 10, padding: '7px 12px', fontSize: 12,
                  borderTop: i === 0 ? 'none' : '1px solid var(--border)',
                  alignItems: 'baseline',
                }}>
                  <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {Number.isInteger(it.quantity) ? it.quantity : it.quantity.toFixed(2)}&times; {it.description}
                  </span>
                  <span className="num" style={{ fontWeight: 600 }}>${it.line_total.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </details>
        )}

        {/* Candidates */}
        <div style={{
          display: 'flex', alignItems: 'center', marginBottom: 8,
        }}>
          <span style={{
            flex: 1, fontSize: 11, fontWeight: 600, color: 'var(--fg-muted)',
            letterSpacing: '0.06em', textTransform: 'uppercase',
          }}>Candidate card transactions</span>
          <select value={windowDays} onChange={e => setWindowDays(Number(e.target.value))} style={{
            padding: '3px 8px', border: '1px solid var(--border)', borderRadius: 6,
            background: 'var(--bg-elev)', color: 'var(--fg-muted)', fontSize: 11, outline: 'none',
          }}>
            <option value={3}>&plusmn;3 days</option>
            <option value={7}>&plusmn;7 days</option>
            <option value={15}>&plusmn;15 days</option>
            <option value={30}>&plusmn;30 days</option>
          </select>
        </div>

        {isLoading && <div style={{ padding: 12, color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>}

        {candidates?.map(c => {
          const diff = c.amount - invoice.total;
          const exact = Math.abs(diff) < 0.01;
          return (
            <div key={c.id} style={{
              border: '1px solid var(--border)', borderRadius: 10,
              padding: '10px 12px', marginBottom: 8,
              display: 'flex', alignItems: 'center', gap: 10,
              background: exact ? 'var(--pos-soft)' : 'var(--bg-elev)',
            }}>
              <div style={{ flex: 1, minWidth: 0, lineHeight: 1.3 }}>
                <div style={{ fontSize: 13, fontWeight: 550, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {c.merchant}
                </div>
                <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
                  {c.bank}{c.card_last ? ` ···${c.card_last}` : ''} &middot; <span className="num">{fmtDate(c.purchased_at)}</span>
                  {c.registered_txn_id && <> &middot; txn #{c.registered_txn_id}</>}
                </div>
              </div>
              <div style={{ textAlign: 'right', lineHeight: 1.3 }}>
                <div className="num" style={{ fontSize: 13.5, fontWeight: 600 }}>{fmtMoney(-c.amount)}</div>
                <div className="num" style={{
                  fontSize: 10.5, fontWeight: 600,
                  color: exact ? 'var(--pos)' : 'var(--warn)',
                }}>
                  {exact ? 'exact' : `${diff > 0 ? '+' : '−'}$${Math.abs(diff).toFixed(2)}`}
                </div>
              </div>
              <button
                onClick={() => linkMut.mutate(c.id)}
                disabled={linkMut.isPending}
                style={{
                  padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 600,
                  background: exact ? 'var(--pos)' : 'transparent',
                  border: exact ? 'none' : '1px solid var(--accent)',
                  color: exact ? 'white' : 'var(--accent)',
                  cursor: 'pointer', opacity: linkMut.isPending ? 0.6 : 1,
                }}
              >Link</button>
            </div>
          );
        })}

        {candidates && candidates.length === 0 && !isLoading && (
          <div style={{ padding: '16px 0', textAlign: 'center', color: 'var(--fg-faint)', fontSize: 13 }}>
            No unmatched card transactions within &plusmn;{windowDays} days.
            <br />Likely paid cash or by another person.
          </div>
        )}

        {linkMut.error && (
          <div style={{ marginTop: 8, fontSize: 12, color: 'var(--neg)' }}>{linkMut.error.message}</div>
        )}
      </div>
    </div>
  );
}
