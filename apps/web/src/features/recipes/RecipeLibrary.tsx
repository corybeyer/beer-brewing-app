import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Badge, Button, Card, CardFooter, EmptyState, InlineNote, PageHeading,
  SearchField, SelectField, TextField, TextAreaField,
} from '@brewery/ui';
import { Icon } from '@brewery/design-system/icons';
import {
  createDraft, listDrafts, loadDraft, newCreationId, RecipeRequestError, saveOverview,
  type RecipeOverview,
} from '@brewery/communications/recipes';
import './RecipeLibrary.css';

type Selection = { kind: 'create' } | { kind: 'open'; id: string };
const pendingKey = 'brewery.pending-draft-creation.v1';
function storedKey(): string | null {
  try { const value = sessionStorage.getItem(pendingKey); return value && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value) ? value : null; } catch { return null; }
}
function rememberKey(value: string | null) {
  try { if (value) sessionStorage.setItem(pendingKey, value); else sessionStorage.removeItem(pendingKey); } catch { /* Memory still retains the current request. */ }
}
function requestError(error: unknown): RecipeRequestError {
  return error instanceof RecipeRequestError ? error : new RecipeRequestError('unavailable', 'The recipe request could not be completed. Please retry.');
}

export function RecipeLibrary({ active = true }: { active?: boolean }) {
  const [items, setItems] = useState<RecipeOverview[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [listState, setListState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [listError, setListError] = useState('');
  const [selected, setSelected] = useState<RecipeOverview | null>(null);
  const [name, setName] = useState(''); const [description, setDescription] = useState('');
  const [busy, setBusy] = useState<'create' | 'open' | 'save' | 'review' | null>(null);
  const [error, setError] = useState<RecipeRequestError | null>(null);
  const [notice, setNotice] = useState('');
  const [conflict, setConflict] = useState(false);
  const [latest, setLatest] = useState<RecipeOverview | null>(null);
  const [pendingSelection, setPendingSelection] = useState<Selection | null>(null);
  const creationId = useRef<string | null>(storedKey());
  const listController = useRef<AbortController | null>(null);
  const actionController = useRef<AbortController | null>(null);
  const focusRequested = useRef(false);
  const dirty = selected !== null && (name !== (selected.name ?? '') || description !== (selected.description ?? ''));

  const refresh = useCallback(async (offset = 0) => {
    listController.current?.abort(); const controller = new AbortController(); listController.current = controller;
    setListState('loading'); setListError('');
    try {
      const page = await listDrafts(controller.signal, offset);
      if (!controller.signal.aborted) {
        setItems((old) => offset === 0 ? page.items : [...old, ...page.items.filter((item) => !old.some((existing) => existing.version_id === item.version_id))]);
        setNextOffset(page.next_offset); setListState('ready');
      }
    } catch (failure) {
      if (!controller.signal.aborted) { setListError(requestError(failure).message); setListState('error'); }
    }
  }, []);

  useEffect(() => { if (active) void refresh(); }, [active, refresh]);
  useEffect(() => () => { listController.current?.abort(); actionController.current?.abort(); }, []);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  useEffect(() => { if (pendingSelection) document.getElementById('keep-recipe-editing')?.focus(); }, [pendingSelection]);
  useEffect(() => {
    if (active && busy === null && selected && focusRequested.current) {
      focusRequested.current = false;
      document.getElementById('recipe-name')?.focus();
    }
  }, [active, busy, selected]);

  function show(draft: RecipeOverview) {
    focusRequested.current = true;
    setSelected(draft); setName(draft.name ?? ''); setDescription(draft.description ?? '');
    setConflict(false); setLatest(null); setNotice('');
  }
  async function run(kind: NonNullable<typeof busy>, work: (signal: AbortSignal) => Promise<RecipeOverview>, apply: (value: RecipeOverview) => void) {
    actionController.current?.abort(); const controller = new AbortController(); actionController.current = controller;
    setBusy(kind); if (kind !== 'review') setError(null); setNotice('');
    try { const value = await work(controller.signal); if (!controller.signal.aborted) apply(value); }
    catch (failure) { if (!controller.signal.aborted) { const problem = requestError(failure); setError(problem); if (problem.code === 'conflict') setConflict(true); } }
    finally { if (!controller.signal.aborted) setBusy(null); }
  }
  function perform(selection: Selection) {
    setPendingSelection(null);
    if (selection.kind === 'open') {
      void run('open', (signal) => loadDraft(selection.id, signal), show);
    } else {
      const key = creationId.current ?? newCreationId(); creationId.current = key; rememberKey(key);
      void run('create', (signal) => createDraft(key, signal), (draft) => {
        listController.current?.abort(); setListState('ready'); setListError('');
        creationId.current = null; rememberKey(null);
        setItems((old) => [draft, ...old.filter((item) => item.version_id !== draft.version_id)]);
        setNextOffset((offset) => offset === null ? null : offset + 1);
        show(draft); setNotice('New draft created. Add a name and description when you are ready.');
      });
    }
  }
  function choose(selection: Selection) {
    if (selection.kind === 'open' && selection.id === selected?.version_id) return;
    if (dirty) setPendingSelection(selection); else perform(selection);
  }
  function save() {
    if (!selected) return;
    void run('save', (signal) => saveOverview(selected, name, description, signal), (draft) => {
      listController.current?.abort(); setListState('ready'); setListError('');
      show(draft); setItems((old) => old.map((item) => item.version_id === draft.version_id ? draft : item)); setNotice('Draft overview saved.');
    });
  }
  function acceptLatest(keepValues: boolean) {
    if (!latest) return;
    if (keepValues) { focusRequested.current = true; setSelected(latest); setConflict(false); setLatest(null); setNotice('Latest version reviewed. Your values are still here; save when ready.'); }
    else { show(latest); setNotice('Latest saved values loaded.'); }
    setError(null);
  }
  const fieldError = (path: string) => error?.issues.find((issue) => issue.path === path)?.message;

  return <>
    <PageHeading headingId={active ? 'page-title' : 'recipe-page-title'} eyebrow="A little planning. A better brew." title="Recipe library"
      description="A home for your recipes, experiments, and next great batch."
      action={<Button busy={busy === 'create'} disabled={busy !== null || listState !== 'ready' && !creationId.current}
        onClick={() => choose({ kind: 'create' })}><Icon name="plus" />{busy === 'create' ? 'Creating draft…' : creationId.current ? 'Retry new draft' : 'New recipe'}</Button>} />

    {pendingSelection && <Card className="content-card" role="alert"><h2>Keep your unsaved changes?</h2>
      <p>Your current draft has changes that have not been saved.</p><div className="recipe-actions">
        <Button id="keep-recipe-editing" onClick={() => { setPendingSelection(null); document.getElementById('recipe-name')?.focus(); }}>Keep editing</Button>
        <Button variant="secondary" onClick={() => perform(pendingSelection)}>Discard changes and continue</Button>
      </div></Card>}
    <p aria-live="polite">{notice}</p>
    {error && <Card className="content-card" role="alert"><h2>{conflict ? 'This draft changed elsewhere' : 'Recipe request needs attention'}</h2>
      <p>{error.message}</p>{conflict && <Button variant="secondary" busy={busy === 'review'} disabled={busy !== null}
        onClick={() => selected && void run('review', (signal) => loadDraft(selected.version_id, signal), (draft) => {
          setLatest(draft); setError(null); setNotice('Latest saved version loaded for review. Your values have not been changed.');
        })}>Review latest saved version</Button>}
    </Card>}

    <div className="library-layout">
      <Card clip aria-label="Saved recipe drafts">
        <div className="form-toolbar">
          <SearchField label="Search recipes" placeholder="Search recipes…" disabled aria-describedby="recipe-availability" />
          <SelectField label="Filter by style" disabled aria-describedby="recipe-availability"><option>All styles</option></SelectField>
        </div>
        <div className="recipe-list" aria-busy={listState === 'loading'}>
          {listState === 'loading' && <p aria-live="polite">Loading recipe drafts…</p>}
          {listError && <div role="alert"><p>{listError}</p>{items.length > 0 && <p>Showing the last loaded draft list.</p>}
            <Button variant="secondary" onClick={() => void refresh()}>Retry loading drafts</Button></div>}
          {listState === 'ready' && items.length === 0 && <EmptyState badge="Room for something good"
            title="Every good batch starts with a recipe." description="Create a draft and start with a name and your notes." />}
          {items.map((draft) => <Card className="content-card" key={draft.version_id}>
            <Badge>Draft · Version {draft.version_number}</Badge><h2>{draft.name ?? 'Untitled draft'}</h2>
            <Button variant="secondary" disabled={busy !== null} aria-label={`Open ${draft.name ?? 'untitled draft'}`}
              onClick={() => choose({ kind: 'open', id: draft.version_id })}>{selected?.version_id === draft.version_id ? 'Editing this draft' : 'Open draft'}</Button>
          </Card>)}
          <div className="recipe-actions"><Button variant="secondary" busy={listState === 'loading'} onClick={() => void refresh()}>Refresh drafts</Button>
            {nextOffset !== null && <Button variant="secondary" disabled={listState !== 'ready'} onClick={() => void refresh(nextOffset)}>Load more drafts</Button>}</div>
        </div>
        <CardFooter icon="lock">Your brewing records belong on your home network.</CardFooter>
      </Card>

      <aside aria-label="Recipe overview editor">
        {selected ? <Card className="content-card"><Badge>Draft · Version {selected.version_number}</Badge><h2>Recipe overview</h2>
          <p className="muted">A name and a little context are enough to start. Incomplete drafts stay drafts.</p>
          {latest && <Card className="content-card" aria-label="Latest saved overview" aria-live="polite"><h3>Latest saved version</h3>
            <p><strong>{latest.name ?? 'Untitled draft'}</strong></p><p>{latest.description ?? 'No description saved.'}</p>
            <div className="recipe-actions"><Button disabled={busy !== null} onClick={() => acceptLatest(true)}>Keep my values</Button>
              <Button variant="secondary" disabled={busy !== null} onClick={() => acceptLatest(false)}>Use saved values</Button></div></Card>}
          <form className="recipe-form" onSubmit={(event) => { event.preventDefault(); if (!busy && dirty && !conflict) save(); }}>
            <TextField id="recipe-name" label="Recipe name" hint="Optional · up to 200 characters" maxLength={200}
              value={name} disabled={busy !== null} error={fieldError('name')} onChange={(event) => setName(event.target.value)} />
            <TextAreaField label="Description" hint="Your idea, goals, or notes · up to 10,000 characters" maxLength={10000}
              value={description} disabled={busy !== null} error={fieldError('description')} onChange={(event) => setDescription(event.target.value)} />
            <p className="muted small" aria-live="polite">{dirty ? 'Unsaved changes' : 'Saved draft overview'}</p>
            <Button type="submit" busy={busy === 'save'} disabled={busy !== null || !dirty || conflict}>{busy === 'save' ? 'Saving…' : 'Save overview'}</Button>
          </form>
        </Card> : <Card className="content-card"><h2>Start with the idea.</h2><p className="muted">Create a recipe or open a saved draft to give it a name and description.</p></Card>}
        <p id="recipe-availability" className="muted small">Name and description editing are available. Search, style, ingredients, steps, targets, imports, and publishing are not editable yet.</p>
        <InlineNote icon="shield">Advice for your brew.<br /><strong>You’re always in control.</strong></InlineNote>
      </aside>
    </div>
  </>;
}
