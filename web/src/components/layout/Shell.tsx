import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import type { ReactNode } from 'react';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: IconDashboard },
  { to: '/transactions', label: 'Transactions', icon: IconList },
  { to: '/review', label: 'Review', icon: IconInbox },
  { to: '/invoices', label: 'Invoices', icon: IconReceipt },
];

const MANAGE_ITEMS = [
  { to: '/subscriptions', label: 'Subscriptions', icon: IconWallet },
  { to: '/accounts', label: 'Accounts', icon: IconWallet },
  { to: '/categories', label: 'Categories', icon: IconTag },
];

const BOTTOM_ITEMS = [
  { to: '/settings', label: 'Settings', icon: IconGear },
];

export default function Shell() {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />
      <main style={{ flex: 1, overflow: 'auto', background: 'var(--bg)' }}>
        <Outlet />
      </main>
    </div>
  );
}

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const w = collapsed ? 56 : 224;
  return (
    <aside style={{
      width: w, flexShrink: 0,
      background: 'var(--bg)', borderRight: '1px solid var(--border)',
      padding: collapsed ? '14px 6px' : '14px 12px',
      display: 'flex', flexDirection: 'column', gap: 16,
      height: '100%', overflow: 'auto',
      transition: 'width 0.15s ease, padding 0.15s ease',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 8px 8px', justifyContent: collapsed ? 'center' : 'flex-start' }}>
        <button onClick={onToggle} style={{
          width: 26, height: 26, borderRadius: 8,
          background: 'var(--accent)', display: 'grid', placeItems: 'center', flexShrink: 0,
          border: 'none', cursor: 'pointer', padding: 0,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 17l6-6 4 4 8-9"/>
          </svg>
        </button>
        {!collapsed && (
          <div style={{ flex: 1, lineHeight: 1.1 }}>
            <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: '-0.015em' }}>Cash Flow</div>
            <div style={{ fontSize: 11, color: 'var(--fg-faint)' }}>Personal</div>
          </div>
        )}
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {NAV_ITEMS.map(item => <SidebarLink key={item.to} {...item} collapsed={collapsed} />)}
      </nav>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {!collapsed && (
          <div style={{
            fontSize: 10.5, fontWeight: 600, color: 'var(--fg-faint)',
            letterSpacing: '0.07em', textTransform: 'uppercase',
            padding: '4px 10px 6px',
          }}>Manage</div>
        )}
        {MANAGE_ITEMS.map(item => <SidebarLink key={item.to} {...item} collapsed={collapsed} />)}
      </div>

      <div style={{ flex: 1 }} />

      <nav style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {BOTTOM_ITEMS.map(item => <SidebarLink key={item.to} {...item} collapsed={collapsed} />)}
      </nav>
    </aside>
  );
}

function SidebarLink({ to, label, icon: IconComponent, collapsed }: { to: string; label: string; icon: () => ReactNode; collapsed?: boolean }) {
  return (
    <NavLink to={to} end={to === '/'} title={collapsed ? label : undefined} style={({ isActive }) => ({
      display: 'flex', alignItems: 'center', gap: 10, width: '100%',
      padding: '7px 10px', textDecoration: 'none',
      justifyContent: collapsed ? 'center' : 'flex-start',
      background: isActive ? 'var(--bg-hover)' : 'transparent',
      color: isActive ? 'var(--fg)' : 'var(--fg-muted)',
      borderRadius: 8, fontSize: 13.5, fontWeight: isActive ? 550 : 450,
    })}>
      {({ isActive }) => (
        <>
          <span style={{ color: isActive ? 'var(--accent)' : 'var(--fg-faint)' }}>
            <IconComponent />
          </span>
          {!collapsed && <span>{label}</span>}
        </>
      )}
    </NavLink>
  );
}

function IconDashboard() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>
    </svg>
  );
}

function IconList() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
      <circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>
    </svg>
  );
}

function IconInbox() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5 5l-3 7v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3-7z"/>
    </svg>
  );
}

function IconWallet() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3"/><path d="M21 12h-4a2 2 0 0 0 0 4h4"/>
    </svg>
  );
}

function IconTag() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><circle cx="7" cy="7" r="1.2" fill="currentColor"/>
    </svg>
  );
}

function IconReceipt() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2z"/>
      <line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/>
    </svg>
  );
}

function IconGear() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
    </svg>
  );
}
