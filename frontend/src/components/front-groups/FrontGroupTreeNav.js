import React, { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Network, Search } from 'lucide-react';

import { Input } from '../ui/input';

const flattenVisible = (tree, expanded, query) => {
  const stack = [...tree].reverse().map((node) => ({ node, depth: 0 })); const result = [];
  while (stack.length) {
    const current = stack.pop(); const children = current.node.children || [];
    if (!query || current.node.name?.toLowerCase().includes(query)) result.push(current);
    if (query || expanded.has(current.node.front_group_id)) {
      for (let index = children.length - 1; index >= 0; index -= 1) stack.push({ node: children[index], depth: current.depth + 1 });
    }
  }
  return result;
};

export const FrontGroupTreeNav = ({ tree, selectedId, onSelect }) => {
  const [search, setSearch] = useState(''); const [expanded, setExpanded] = useState(() => new Set());
  const query = search.trim().toLowerCase(); const visible = useMemo(() => flattenVisible(tree, expanded, query), [expanded, query, tree]);
  const toggle = (id) => setExpanded((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  return <aside className="border border-slate-200 bg-white" data-testid="front-group-tree-nav"><div className="border-b border-slate-200 p-4"><div className="mb-3 flex items-center gap-2"><Network className="h-4 w-4 text-amber-700" /><h2 className="font-['Spectral'] text-lg font-semibold">Árbol frontal</h2></div><div className="relative"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input value={search} onChange={(event) => setSearch(event.target.value)} className="pl-9" placeholder="Buscar rama" data-testid="front-group-tree-search-input" /></div></div>
    <div className="max-h-[62vh] overflow-y-auto py-2">{visible.map(({ node, depth }) => { const hasChildren = node.children?.length > 0; const isOpen = expanded.has(node.front_group_id) || Boolean(query); return <div key={node.front_group_id} className={`flex items-center border-l-2 ${selectedId === node.front_group_id ? 'border-amber-500 bg-amber-50' : 'border-transparent hover:bg-slate-50'}`} style={{ paddingLeft: `${Math.min(depth, 8) * 12 + 6}px` }} data-testid={`front-group-tree-branch-${node.front_group_id}`}><button type="button" onClick={() => toggle(node.front_group_id)} disabled={!hasChildren} className="grid h-9 w-8 shrink-0 place-items-center text-slate-500 disabled:opacity-20" aria-label={isOpen ? 'Contraer rama' : 'Expandir rama'} data-testid={`front-group-tree-toggle-${node.front_group_id}`}>{isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</button><button type="button" onClick={() => onSelect(node)} className="min-w-0 flex-1 py-3 pr-3 text-left" data-testid={`front-group-tree-node-${node.front_group_id}`}><span className="block truncate text-sm font-semibold text-slate-900">{node.name}</span><span className="block truncate text-xs text-slate-500">{node.primary_leader_name || 'Liderazgo pendiente'} · {node.team_count || 0} personas</span></button></div>; })}{!visible.length && <p className="p-6 text-center text-sm text-slate-500" data-testid="front-group-tree-empty">No hay ramas para mostrar.</p>}</div>
  </aside>;
};