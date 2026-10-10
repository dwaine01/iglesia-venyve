import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Settings, RotateCcw } from 'lucide-react';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '../ui/alert-dialog';

export const CampaignSettingsPanel = ({ base, getAuthHeaders, settings, onChanged }) => {
  const [goalInput, setGoalInput] = useState((settings.goal_cents / 100).toFixed(2));
  const [countingRule, setCountingRule] = useState(settings.counting_rule);
  const [pendingMode, setPendingMode] = useState(null);
  const [saving, setSaving] = useState(false);

  const save = async (modeOverride) => {
    setSaving(true);
    try {
      await axios.put(`${base}/settings`, {
        goal_cents: Math.round(parseFloat(goalInput || 0) * 100),
        counting_rule: countingRule,
        mode: modeOverride || settings.mode,
      }, getAuthHeaders());
      toast.success('Configuración actualizada');
      await onChanged();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo guardar la configuración');
    } finally {
      setSaving(false);
    }
  };

  const resetRehearsal = async () => {
    try {
      await axios.post(`${base}/settings/reset-rehearsal`, {}, getAuthHeaders());
      toast.success('Datos de ensayo reiniciados');
      await onChanged();
    } catch (err) {
      toast.error('No se pudo reiniciar el ensayo');
    }
  };

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5" data-testid="campaign-settings-panel">
      <h3 className="flex items-center gap-2 font-serif text-lg text-[#132443]"><Settings className="h-4 w-4" />Configuración de campaña</h3>

      <div>
        <Label>Meta (USD)</Label>
        <Input type="number" min="1" step="1" value={goalInput} onChange={(e) => setGoalInput(e.target.value)} data-testid="campaign-goal-input" />
      </div>

      <div>
        <Label>Regla de progreso</Label>
        <Select value={countingRule} onValueChange={setCountingRule}>
          <SelectTrigger data-testid="campaign-counting-rule-select"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-white">
            <SelectItem value="committed">Comprometido (recibido + promesas)</SelectItem>
            <SelectItem value="received_only">Solo recibido</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label>Modo</Label>
        <Select value={settings.mode} onValueChange={(value) => {
          if (value === 'production' && settings.mode !== 'production') { setPendingMode(value); return; }
          save(value);
        }}>
          <SelectTrigger data-testid="campaign-mode-select"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-white">
            <SelectItem value="rehearsal">Ensayo</SelectItem>
            <SelectItem value="production">Producción</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Button variant="outline" className="w-full" disabled={saving} onClick={() => save()} data-testid="campaign-save-settings-button">Guardar configuración</Button>

      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button variant="ghost" className="w-full text-red-600" data-testid="campaign-reset-rehearsal-button"><RotateCcw className="h-4 w-4" />Reiniciar datos de ensayo</Button>
        </AlertDialogTrigger>
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle>¿Reiniciar el modo ensayo?</AlertDialogTitle>
            <AlertDialogDescription>Se borrarán todos los donativos marcados como ensayo. Los datos reales de producción no se tocan.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={resetRehearsal} data-testid="campaign-reset-rehearsal-confirm">Reiniciar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={Boolean(pendingMode)} onOpenChange={(open) => !open && setPendingMode(null)}>
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle>¿Cambiar a modo PRODUCCIÓN?</AlertDialogTitle>
            <AlertDialogDescription>A partir de ahora los donativos registrados serán datos reales de la campaña, visibles en la pantalla pública.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingMode(null)} data-testid="campaign-production-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={() => { save('production'); setPendingMode(null); }} data-testid="campaign-production-confirm">Confirmar producción</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
