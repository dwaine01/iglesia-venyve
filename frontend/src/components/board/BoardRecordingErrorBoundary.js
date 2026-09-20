import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

import { Button } from '../ui/button';

export class BoardRecordingErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { failed: false }; }
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error) { console.error('Board recording workspace failed', error); }
  render() {
    if (!this.state.failed) return this.props.children;
    return <section className="border border-red-200 bg-red-50 p-6 text-red-900" data-testid="board-recording-workspace-error"><AlertTriangle className="h-6 w-6" /><h2 className="mt-3 font-semibold">No se pudo mostrar el espacio de grabación</h2><p className="mt-1 text-sm">La reunión continúa abierta. Recargue este espacio para recuperar los controles.</p><Button className="mt-4" variant="outline" onClick={() => window.location.reload()} data-testid="reload-board-recording-workspace-button"><RefreshCw className="mr-2 h-4 w-4" />Recargar grabación</Button></section>;
  }
}