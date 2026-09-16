/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

import { FinanceBatchesPanel } from '../../components/finance/FinanceBatchesPanel';
import { FinanceCampaignsPanel } from '../../components/finance/FinanceCampaignsPanel';
import { FinancePayablesPanel } from '../../components/finance/FinancePayablesPanel';
import { FinancePlanningPanel } from '../../components/finance/FinancePlanningPanel';
import { FinanceRecurringPanel } from '../../components/finance/FinanceRecurringPanel';
import { FinanceShell } from '../../components/finance/FinanceShell';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useAuth } from '../../context/AuthContext';

export default function FinanceOperationsPage() {
  const { API, getAuthHeaders } = useAuth();
  const [catalog, setCatalog] = useState({ funds: [], accounts: [] });
  const [vendors, setVendors] = useState([]);
  const loadVendors = () => axios.get(`${API}/api/finance/vendors`, getAuthHeaders()).then((response) => setVendors(response.data.items || []));
  useEffect(() => { Promise.all([axios.get(`${API}/api/finance/catalog`, getAuthHeaders()).then((response) => setCatalog(response.data)), loadVendors()]).catch(() => toast.error('No se pudo cargar Operación')); }, []);
  return <FinanceShell title="Operación financiera" description="Contar, depositar, pagar y anticipar obligaciones dentro del mismo libro contable."><Tabs defaultValue="counts"><TabsList className="h-auto flex-wrap justify-start" data-testid="finance-operations-tabs"><TabsTrigger value="counts" data-testid="operations-counts-tab">Conteos y depósitos</TabsTrigger><TabsTrigger value="payables" data-testid="operations-payables-tab">Cuentas por pagar</TabsTrigger><TabsTrigger value="recurring" data-testid="operations-recurring-tab">Recurrentes</TabsTrigger><TabsTrigger value="planning" data-testid="operations-planning-tab">Presupuesto y fondos</TabsTrigger><TabsTrigger value="campaigns" data-testid="operations-campaigns-tab">Proyectos y campañas</TabsTrigger></TabsList><TabsContent value="counts" className="mt-5"><FinanceBatchesPanel /></TabsContent><TabsContent value="payables" className="mt-5"><FinancePayablesPanel catalog={catalog} vendors={vendors} refreshVendors={loadVendors} /></TabsContent><TabsContent value="recurring" className="mt-5"><FinanceRecurringPanel catalog={catalog} vendors={vendors} /></TabsContent><TabsContent value="planning" className="mt-5"><FinancePlanningPanel catalog={catalog} /></TabsContent><TabsContent value="campaigns" className="mt-5"><FinanceCampaignsPanel funds={catalog.funds} /></TabsContent></Tabs></FinanceShell>;
}