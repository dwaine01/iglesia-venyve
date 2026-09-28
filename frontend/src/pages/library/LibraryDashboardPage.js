import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, ArrowRight, BookOpen, PackageCheck, Users } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { canManageLibraryInventory, canViewLibraryPurchaseOrders, canViewLibraryModule, canViewLibraryReports } from '../../lib/accessControl';
import { Badge } from '../../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { LibrarianManagerPanel } from '../../components/library/LibrarianManagerPanel';
import { BookThumbnail } from '../../components/library/BookThumbnail';
import { LibraryNotificationsBell } from '../../components/library/LibraryNotificationsBell';

const STATUS_BADGE = { critico: 'bg-red-100 text-red-700', bajo: 'bg-amber-100 text-amber-700', suficiente: 'bg-emerald-100 text-emerald-700' };
const STATUS_LABEL = { critico: '🔴 Stock crítico', bajo: '🟠 Stock bajo', suficiente: '🟢 Stock suficiente' };

export default function LibraryDashboardPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [inventory, setInventory] = useState([]);
  const isManager = canManageLibraryInventory(user);
  const canSeePOs = canViewLibraryPurchaseOrders(user);

  const refresh = useCallback(async () => {
    const { data } = await axios.get(`${API}/api/library/dashboard`, getAuthHeaders());
    setDashboard(data);
    if (isManager) {
      const inv = await axios.get(`${API}/api/library/inventory`, getAuthHeaders());
      setInventory(inv.data.items || []);
    }
  }, [API, isManager]);

  useEffect(() => { refresh(); }, [refresh]);

  return <main className="min-h-screen bg-[#F4F1EA] px-4 py-6 sm:px-8" data-testid="library-dashboard-page">
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="font-serif text-3xl text-[#132443]">Librería 360</h1><p className="text-sm text-slate-600">Inventario, distribución y trazabilidad de todos los materiales educativos.</p></div>
        <div className="flex items-center gap-2">
          <LibraryNotificationsBell />
          <Link to="/libreria/mi-inventario" className="rounded-lg border border-[#132443] px-4 py-2 text-sm text-[#132443]" data-testid="link-my-library-inventory">Mi inventario</Link>
          <Link to="/libreria/escanear" className="rounded-lg border border-[#132443] px-4 py-2 text-sm text-[#132443]" data-testid="link-library-scan">Escanear</Link>
          {canViewLibraryReports(user) && <Link to="/libreria/reportes" className="rounded-lg border border-[#132443] px-4 py-2 text-sm text-[#132443]" data-testid="link-library-reports">Reportes</Link>}
          {isManager && <Link to="/libreria/catalogo" className="rounded-lg border border-[#132443] px-4 py-2 text-sm text-[#132443]" data-testid="link-library-catalog">Catálogo</Link>}
          {isManager && <Link to="/libreria/etiquetas" className="rounded-lg border border-[#132443] px-4 py-2 text-sm text-[#132443]" data-testid="link-library-labels">Etiquetas</Link>}
          {isManager && <Link to="/libreria/reserva-automatica" className="rounded-lg border border-[#132443] px-4 py-2 text-sm text-[#132443]" data-testid="link-library-deficit">Reserva Automática</Link>}
          {canSeePOs && <Link to="/libreria/ordenes-compra" className="rounded-lg bg-[#132443] px-4 py-2 text-sm text-white" data-testid="link-library-purchase-orders">Órdenes de compra <ArrowRight className="ml-1 inline h-4 w-4" /></Link>}
        </div>
      </header>

      {dashboard && <div className="grid gap-4 sm:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="library-total-registered"><PackageCheck className="h-5 w-5 text-[#0879BE]" /><p className="mt-2 text-2xl font-semibold">{dashboard.totals.registered}</p><p className="text-xs text-slate-500">materiales registrados</p></div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="library-total-available"><BookOpen className="h-5 w-5 text-emerald-600" /><p className="mt-2 text-2xl font-semibold">{dashboard.totals.available}</p><p className="text-xs text-slate-500">disponibles en central</p></div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="library-total-with-leaders"><Users className="h-5 w-5 text-amber-600" /><p className="mt-2 text-2xl font-semibold">{dashboard.totals.with_leaders}</p><p className="text-xs text-slate-500">en poder de líderes</p></div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="library-total-delivered"><BookOpen className="h-5 w-5 text-[#132443]" /><p className="mt-2 text-2xl font-semibold">{dashboard.totals.delivered}</p><p className="text-xs text-slate-500">entregados a personas</p></div>
      </div>}

      {dashboard && (dashboard.alerts.critical.length > 0 || dashboard.alerts.low.length > 0 || dashboard.alerts.overdue_purchase_orders > 0) && <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4" data-testid="library-alerts-panel">
        <p className="flex items-center gap-2 font-medium text-amber-800"><AlertTriangle className="h-4 w-4" />Alertas de inventario</p>
        {dashboard.alerts.critical.length > 0 && <p className="mt-1 text-sm text-red-700">🔴 Stock crítico: {dashboard.alerts.critical.join(', ')}</p>}
        {dashboard.alerts.low.length > 0 && <p className="mt-1 text-sm text-amber-700">🟠 Stock bajo: {dashboard.alerts.low.join(', ')}</p>}
        {dashboard.alerts.overdue_purchase_orders > 0 && <p className="mt-1 text-sm text-red-700" data-testid="library-overdue-po-alert">📦 {dashboard.alerts.overdue_purchase_orders} orden(es) de compra retrasada(s) — <Link to="/libreria/ordenes-compra" className="underline">ver detalle</Link></p>}
      </div>}

      {isManager && <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="library-inventory-panel">
        <h2 className="font-serif text-lg text-[#132443]">Inventario por material</h2>
        <Table className="mt-3"><TableHeader><TableRow><TableHead /><TableHead>Material</TableHead><TableHead>Disponible</TableHead><TableHead>Reservado</TableHead><TableHead>Con líderes</TableHead><TableHead>Entregado</TableHead><TableHead>Stock mínimo</TableHead><TableHead>Estado</TableHead></TableRow></TableHeader>
          <TableBody>{inventory.map((item) => <TableRow key={item.book_id} data-testid={`library-inventory-row-${item.book_id}`}>
            <TableCell><BookThumbnail fileId={item.cover_file_id} size={32} /></TableCell>
            <TableCell>{item.name}</TableCell><TableCell>{item.available_central}</TableCell><TableCell>{item.reserved_central}</TableCell>
            <TableCell>{item.with_leaders}</TableCell><TableCell>{item.delivered}</TableCell><TableCell>{item.min_stock}</TableCell>
            <TableCell><Badge className={STATUS_BADGE[item.status]}>{STATUS_LABEL[item.status]}</Badge></TableCell>
          </TableRow>)}</TableBody>
        </Table>
      </div>}

      {isManager && <LibrarianManagerPanel />}
    </div>
  </main>;
}
