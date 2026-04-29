// Cash Flow — sample data
// Realistic data spanning ~3 months of personal finance, March-April-May 2026.

const ACCOUNTS = [
  { id: 'cash', name: 'Checking', type: 'cash', color: 'oklch(0.62 0.16 250)' },
  { id: 'cc_visa', name: 'Visa Pichincha', type: 'credit_card', last4: '4471', cutOff: 5, payDay: 22, color: 'oklch(0.62 0.14 30)' },
  { id: 'cc_amex', name: 'Amex Gold',     type: 'credit_card', last4: '8810', cutOff: 12, payDay: 5, color: 'oklch(0.55 0.06 250)' },
];

const ACCOUNT_BY_ID = Object.fromEntries(ACCOUNTS.map(a => [a.id, a]));

const CATEGORIES = ['Groceries', 'Dining', 'Transport', 'Leisure', 'Utilities', 'Subscriptions', 'Housing', 'Health', 'Income', 'Other'];

const BUDGETS = [
  { id: 'b_groceries', name: 'Groceries',  amount: 480, account: 'cc_visa', category: 'Groceries', spent: 312.40, color: 'var(--cat-1)' },
  { id: 'b_dining',    name: 'Dining out', amount: 220, account: 'cc_visa', category: 'Dining',    spent: 184.50, color: 'var(--cat-2)' },
  { id: 'b_transport', name: 'Transport',  amount: 150, account: 'cc_amex', category: 'Transport', spent: 98.20,  color: 'var(--cat-3)' },
  { id: 'b_leisure',   name: 'Leisure',    amount: 200, account: 'cc_visa', category: 'Leisure',   spent: 245.00, color: 'var(--cat-4)' },
  { id: 'b_utilities', name: 'Utilities',  amount: 180, account: 'cash',    category: 'Utilities', spent: 142.30, color: 'var(--cat-5)' },
  { id: 'b_health',    name: 'Health',     amount: 120, account: 'cash',    category: 'Health',    spent: 0,      color: 'oklch(0.62 0.10 0)' },
];

// Transactions for April 2026 (current month, ~22 entries)
// Format: { id, desc, amount, account, category, budget?, date_payed, date_created, status, source?, needs_review? }
const TXNS = [
  // Late March committed
  { id: 1041, desc: 'Salary — April',                   amount: +3400.00, account: 'cash',    category: 'Income',        date_payed: '2026-04-01', date_created: '2026-04-01', status: 'committed' },
  { id: 1042, desc: 'Rent — Calle Amazonas',            amount: -1100.00, account: 'cash',    category: 'Housing',       date_payed: '2026-04-02', date_created: '2026-04-02', status: 'committed' },
  { id: 1043, desc: 'Spotify Family',                   amount: -16.99,   account: 'cc_amex', category: 'Subscriptions', budget: 'Subscriptions',  date_payed: '2026-04-03', date_created: '2026-03-25', status: 'committed' },
  { id: 1044, desc: 'Supermaxi groceries',              amount: -84.20,   account: 'cc_visa', category: 'Groceries',     budget: 'b_groceries',    date_payed: '2026-04-04', date_created: '2026-03-28', status: 'committed' },
  { id: 1045, desc: 'Uber — airport',                   amount: -22.50,   account: 'cc_amex', category: 'Transport',     budget: 'b_transport',    date_payed: '2026-04-05', date_created: '2026-03-29', status: 'committed' },
  { id: 1046, desc: 'Coffee — Isveglio',                amount: -6.40,    account: 'cc_visa', category: 'Dining',        budget: 'b_dining',       date_payed: '2026-04-06', date_created: '2026-03-30', status: 'committed' },
  { id: 1047, desc: 'Electricity — CNEL',               amount: -54.30,   account: 'cash',    category: 'Utilities',     budget: 'b_utilities',    date_payed: '2026-04-08', date_created: '2026-04-08', status: 'committed' },
  { id: 1048, desc: 'Pharmacy — Fybeca',                amount: -18.75,   account: 'cc_visa', category: 'Health',        date_payed: '2026-04-09', date_created: '2026-04-02', status: 'committed' },
  { id: 1049, desc: 'Netflix',                          amount: -14.99,   account: 'cc_amex', category: 'Subscriptions', date_payed: '2026-04-10', date_created: '2026-04-01', status: 'committed' },
  { id: 1050, desc: 'Cinema — Multicines',              amount: -28.00,   account: 'cc_visa', category: 'Leisure',       budget: 'b_leisure',      date_payed: '2026-04-12', date_created: '2026-04-04', status: 'committed' },
  { id: 1051, desc: 'Supermaxi groceries',              amount: -112.80,  account: 'cc_visa', category: 'Groceries',     budget: 'b_groceries',    date_payed: '2026-04-15', date_created: '2026-04-08', status: 'committed' },
  { id: 1052, desc: 'Dinner — La Tablita',              amount: -64.00,   account: 'cc_visa', category: 'Dining',        budget: 'b_dining',       date_payed: '2026-04-16', date_created: '2026-04-09', status: 'committed' },
  { id: 1053, desc: 'Internet — Netlife',               amount: -38.00,   account: 'cash',    category: 'Utilities',     budget: 'b_utilities',    date_payed: '2026-04-18', date_created: '2026-04-18', status: 'committed' },
  { id: 1054, desc: 'Concert — Alaska Live (3/4)',      amount: -75.00,   account: 'cc_visa', category: 'Leisure',       budget: 'b_leisure',      date_payed: '2026-04-22', date_created: '2026-02-10', status: 'committed', origin_id: 'inst_alaska', notes: '4-month installment' },
  { id: 1055, desc: 'Co-working day pass',              amount: -12.00,   account: 'cc_amex', category: 'Other',         date_payed: '2026-04-23', date_created: '2026-04-15', status: 'pending', source: 'gmail', needs_review: true },
  { id: 1056, desc: 'Lunch — Crepes & Waffles',         amount: -19.50,   account: 'cc_visa', category: 'Dining',        budget: 'b_dining',       date_payed: '2026-04-24', date_created: '2026-04-17', status: 'pending', source: 'gmail', needs_review: true },
  { id: 1057, desc: 'Bookstore — Mr. Books',            amount: -32.40,   account: 'cc_visa', category: 'Leisure',       budget: 'b_leisure',      date_payed: '2026-04-25', date_created: '2026-04-19', status: 'pending', source: 'mom',   needs_review: true },
  { id: 1058, desc: 'Gym — Smartfit (May)',             amount: -42.00,   account: 'cc_amex', category: 'Subscriptions', date_payed: '2026-04-28', date_created: '2026-04-20', status: 'planning' },
  { id: 1059, desc: 'Flight to Lima — Avianca',         amount: -312.00,  account: 'cc_visa', category: 'Transport',     date_payed: '2026-05-22', date_created: '2026-04-21', status: 'planning', notes: 'Trip planning' },
  { id: 1060, desc: 'AWS Personal',                     amount: -23.50,   account: 'cc_amex', category: 'Subscriptions', date_payed: '2026-05-05', date_created: '2026-04-22', status: 'forecast' },
  { id: 1061, desc: 'Salary — May',                     amount: +3400.00, account: 'cash',    category: 'Income',        date_payed: '2026-05-01', date_created: '2026-05-01', status: 'forecast' },
  { id: 1062, desc: 'Rent — Calle Amazonas',            amount: -1100.00, account: 'cash',    category: 'Housing',       date_payed: '2026-05-02', date_created: '2026-05-02', status: 'forecast' },
];

// Review queue — needs_review transactions, slightly enriched
const REVIEW_QUEUE = [
  {
    id: 1055, desc: 'Co-working day pass', amount: -12.00, account: 'cc_amex',
    suggestedCategory: 'Other', suggestedBudget: null,
    date: '2026-04-15', source: 'gmail',
    consumo: { merchant: 'IMPAQTO QUITO', card: '8810', purchasedAt: '2026-04-15 10:42', bank: 'Amex' },
    invoice: null,
    llm: { model: 'gemma3:12b', confidence: 0.62, reasoning: 'Generic merchant name, no clear category match. Default to "Other".' },
  },
  {
    id: 1056, desc: 'Crepes & Waffles', amount: -19.50, account: 'cc_visa',
    suggestedCategory: 'Dining', suggestedBudget: 'b_dining',
    date: '2026-04-17', source: 'gmail',
    consumo: { merchant: 'CREPES Y WAFFLES SCC', card: '4471', purchasedAt: '2026-04-17 13:15', bank: 'Pichincha' },
    invoice: { number: '001-001-000123456', vendor: 'CREPES Y WAFFLES S.C.C.', total: 19.50, taxes: 'IVA 12% — $2.34' },
    llm: { model: 'gemma3:12b', confidence: 0.96, reasoning: 'Restaurant chain. Category matches existing "Dining" budget for current month.' },
  },
  {
    id: 1057, desc: 'Bookstore — Mr. Books', amount: -32.40, account: 'cc_visa',
    suggestedCategory: 'Leisure', suggestedBudget: 'b_leisure',
    date: '2026-04-19', source: 'mom',
    consumo: null,
    invoice: null,
    llm: null,
    note: 'Submitted by extra user. Needs owner approval.',
  },
  {
    id: 1063, desc: 'Pharmacy — Sana Sana', amount: -8.20, account: 'cc_visa',
    suggestedCategory: 'Health', suggestedBudget: 'b_health',
    date: '2026-04-20', source: 'gmail',
    consumo: { merchant: 'FCIA SANA SANA 0245', card: '4471', purchasedAt: '2026-04-20 18:30', bank: 'Pichincha' },
    invoice: { number: '003-002-000087412', vendor: 'PHARMACYS SA', total: 8.20, taxes: 'IVA 12% — $0.98' },
    llm: { model: 'gemma3:12b', confidence: 0.91, reasoning: 'Pharmacy chain. Health category, fits unspent Health budget.' },
  },
  {
    id: 1064, desc: 'Gas — Primax', amount: -42.00, account: 'cc_amex',
    suggestedCategory: 'Transport', suggestedBudget: 'b_transport',
    date: '2026-04-21', source: 'gmail',
    consumo: { merchant: 'EP PETROECUADOR PRIMAX', card: '8810', purchasedAt: '2026-04-21 08:11', bank: 'Amex' },
    invoice: null,
    llm: { model: 'gemma3:12b', confidence: 0.88, reasoning: 'Gas station. Transport category. Budget has $51.80 remaining.' },
  },
];

// Daily balance points for the chart — built from TXNS via running balance
function buildBalanceSeries(txns, startBalance = 5240.50) {
  const sorted = [...txns].sort((a, b) => a.date_payed.localeCompare(b.date_payed));
  const byDate = new Map();
  let bal = startBalance;
  for (const t of sorted) {
    if (t.status === 'pending') continue; // pending excluded from running balance
    bal += t.amount;
    byDate.set(t.date_payed, { date: t.date_payed, balance: bal, txns: [...(byDate.get(t.date_payed)?.txns || []), t] });
  }
  return Array.from(byDate.values());
}

const BALANCE_SERIES = buildBalanceSeries(TXNS);

// Account balances (snapshot)
const ACCOUNT_BALANCES = {
  cash:    { current: 4218.30, available: 4218.30 },
  cc_visa: { current: -842.40, available: 4157.60, limit: 5000, dueDate: '2026-04-22', minPay: 84.24 },
  cc_amex: { current: -184.30, available: 2815.70, limit: 3000, dueDate: '2026-05-05', minPay: 18.43 },
};

// ─── Invoices ───────────────────────────────────────────────────────────────
// Linked to TXNS by id. Mirrors the structure of an electronic invoice
// (factura electrónica) — header info, line items, taxes, totals, payment method.

const INVOICES = {
  // Supermaxi groceries — id 1044
  1044: {
    number: '001-002-000084217',
    auth: '2604202601179...4217', // 49-digit auth code (truncated for display)
    issuedAt: '2026-04-04 19:12',
    vendor: { name: 'CORPORACIÓN FAVORITA C.A.', tradeName: 'Supermaxi', taxId: '1790016919001', address: 'Av. Granados N40-53, Quito' },
    customer: { name: 'Andrés Mendoza',     taxId: '1712345678', email: 'andres.m@example.com' },
    paymentMethod: 'Tarjeta de crédito · Visa ··4471',
    items: [
      { sku: '7861000610015', name: 'Leche entera 1L · La Vaquita', qty: 4,  price: 1.05, tax: 0,    discount: 0 },
      { sku: '7861001230018', name: 'Pan integral 500g',            qty: 2,  price: 2.40, tax: 0,    discount: 0 },
      { sku: '7861002340021', name: 'Pollo entero · 1.8kg',         qty: 1,  price: 9.85, tax: 0,    discount: 0 },
      { sku: '7861003450034', name: 'Huevos AA × 30u',              qty: 1,  price: 5.20, tax: 0,    discount: 0 },
      { sku: '7861004560047', name: 'Arroz Gustadina 2kg',          qty: 2,  price: 2.95, tax: 0,    discount: 0 },
      { sku: '7861005670050', name: 'Aceite de girasol 1L',         qty: 1,  price: 4.65, tax: 0.56, discount: 0 },
      { sku: '7861006780063', name: 'Detergente Deja 1kg',          qty: 1,  price: 6.10, tax: 0.73, discount: 0 },
      { sku: '7861007890076', name: 'Papel higiénico × 12u',        qty: 1,  price: 8.90, tax: 1.07, discount: 0 },
      { sku: '7861008900089', name: 'Manzanas rojas · kg',          qty: 1.4, price: 2.30, tax: 0,   discount: 0 },
      { sku: '7861009010092', name: 'Tomate riñón · kg',            qty: 0.8, price: 1.20, tax: 0,   discount: 0 },
      { sku: '7861010120105', name: 'Yogurt natural 1L',            qty: 2,  price: 3.10, tax: 0,    discount: 0 },
      { sku: '7861011230118', name: 'Galletas Oreo 132g',           qty: 3,  price: 1.45, tax: 0.17, discount: 0.30 },
    ],
    subtotal12: 22.27,  // taxable items subtotal
    subtotal0: 59.43,   // 0% taxable subtotal
    discount: 0.30,
    iva: 2.53,          // IVA 12%
    tip: 0,
    total: 84.20,
  },

  // Cinema — id 1050
  1050: {
    number: '004-001-000031450',
    auth: '1204202601245...1450',
    issuedAt: '2026-04-12 20:35',
    vendor: { name: 'MULTICINES S.A.', tradeName: 'Multicines CCI', taxId: '1791250963001', address: 'C.C.I., Av. Amazonas, Quito' },
    customer: { name: 'Andrés Mendoza', taxId: '1712345678', email: 'andres.m@example.com' },
    paymentMethod: 'Tarjeta de crédito · Visa ··4471',
    items: [
      { sku: 'TKT-PREM',  name: 'Entrada Premium · Sala 6',         qty: 2, price: 8.50, tax: 1.02, discount: 0 },
      { sku: 'COMBO-DUO', name: 'Combo dúo (canguil + 2 bebidas)',  qty: 1, price: 9.80, tax: 1.18, discount: 0 },
      { sku: 'NACHO',     name: 'Nachos con queso',                 qty: 1, price: 1.20, tax: 0.14, discount: 0 },
    ],
    subtotal12: 27.50,
    subtotal0: 0,
    discount: 0,
    iva: 3.30,
    tip: 0,
    total: 28.00,
  },

  // Dinner — id 1052
  1052: {
    number: '002-001-000019874',
    auth: '1604202601327...9874',
    issuedAt: '2026-04-16 21:48',
    vendor: { name: 'LA TABLITA DEL TÁRTARO CIA. LTDA.', tradeName: 'La Tablita', taxId: '1791832104001', address: 'Av. González Suárez N32-150, Quito' },
    customer: { name: 'Andrés Mendoza', taxId: '1712345678', email: 'andres.m@example.com' },
    paymentMethod: 'Tarjeta de crédito · Visa ··4471',
    items: [
      { sku: 'LOMO-FNO',  name: 'Lomo fino 350g (al punto)',  qty: 1, price: 22.50, tax: 2.70, discount: 0 },
      { sku: 'PASTA-BLG', name: 'Pasta boloñesa',             qty: 1, price: 12.80, tax: 1.54, discount: 0 },
      { sku: 'ENS-CSR',   name: 'Ensalada César',             qty: 1, price:  7.50, tax: 0.90, discount: 0 },
      { sku: 'VINO-COP',  name: 'Copa de vino Malbec',        qty: 2, price:  5.20, tax: 0.62, discount: 0 },
      { sku: 'POSTRE',    name: 'Cheesecake de frutos rojos', qty: 1, price:  4.80, tax: 0.58, discount: 0 },
      { sku: 'AGUA',      name: 'Agua sin gas 500ml',         qty: 2, price:  1.50, tax: 0.18, discount: 0 },
    ],
    subtotal12: 53.20,
    subtotal0: 0,
    discount: 0,
    iva: 6.38,
    tip: 4.42,            // 10% service
    total: 64.00,
  },

  // Pharmacy — id 1048
  1048: {
    number: '003-002-000087412',
    auth: '0904202601198...7412',
    issuedAt: '2026-04-09 11:22',
    vendor: { name: 'PHARMACYS S.A.', tradeName: 'Fybeca', taxId: '1790012345001', address: 'Av. 6 de Diciembre N34-12, Quito' },
    customer: { name: 'Andrés Mendoza', taxId: '1712345678', email: 'andres.m@example.com' },
    paymentMethod: 'Tarjeta de crédito · Visa ··4471',
    items: [
      { sku: 'IBU-400',  name: 'Ibuprofeno 400mg × 20',     qty: 1, price: 4.20, tax: 0,    discount: 0 },
      { sku: 'VITA-C',   name: 'Vitamina C 1g × 30',        qty: 1, price: 8.90, tax: 0,    discount: 0 },
      { sku: 'BAND-AID', name: 'Curitas plásticas × 30',    qty: 1, price: 3.10, tax: 0.37, discount: 0 },
      { sku: 'ALCO-70',  name: 'Alcohol antiséptico 250ml', qty: 1, price: 2.18, tax: 0,    discount: 0 },
    ],
    subtotal12: 3.10,
    subtotal0: 15.28,
    discount: 0,
    iva: 0.37,
    tip: 0,
    total: 18.75,
  },

  // Bookstore — id 1057 (also in REVIEW_QUEUE)
  1057: {
    number: '005-001-000004821',
    auth: '1904202601412...4821',
    issuedAt: '2026-04-19 17:05',
    vendor: { name: 'LIBRESA CIA. LTDA.', tradeName: 'Mr. Books — Quicentro', taxId: '1790054321001', address: 'C.C. Quicentro, Av. 6 de Diciembre, Quito' },
    customer: { name: 'Andrés Mendoza', taxId: '1712345678', email: 'andres.m@example.com' },
    paymentMethod: 'Tarjeta de crédito · Visa ··4471',
    items: [
      { sku: 'BK-9788437604947', name: 'Cien años de soledad — G. García Márquez', qty: 1, price: 18.90, tax: 0, discount: 0 },
      { sku: 'BK-9788491817222', name: 'El infinito en un junco — Irene Vallejo',  qty: 1, price: 13.50, tax: 0, discount: 0 },
    ],
    subtotal12: 0,
    subtotal0: 32.40,
    discount: 0,
    iva: 0,
    tip: 0,
    total: 32.40,
  },

  // Co-working — id 1055
  1055: {
    number: '001-001-000005612',
    auth: '1504202601112...5612',
    issuedAt: '2026-04-15 10:42',
    vendor: { name: 'IMPAQTO QUITO S.A.', tradeName: 'Impaqto Coworking', taxId: '1792513684001', address: 'Av. La Coruña N27-23, Quito' },
    customer: { name: 'Andrés Mendoza', taxId: '1712345678', email: 'andres.m@example.com' },
    paymentMethod: 'Tarjeta de crédito · Amex ··8810',
    items: [
      { sku: 'DAY-PASS', name: 'Day pass — Hot desk', qty: 1, price: 10.71, tax: 1.29, discount: 0 },
    ],
    subtotal12: 10.71,
    subtotal0: 0,
    discount: 0,
    iva: 1.29,
    tip: 0,
    total: 12.00,
  },
};

// Add `has_invoice: true` to txns whose id is a key of INVOICES so the row knows.
TXNS.forEach(t => { if (INVOICES[t.id]) t.has_invoice = true; });

Object.assign(window, {
  ACCOUNTS, ACCOUNT_BY_ID, CATEGORIES, BUDGETS, TXNS, REVIEW_QUEUE, BALANCE_SERIES, ACCOUNT_BALANCES, INVOICES,
});
