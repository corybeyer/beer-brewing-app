import { useState } from 'react';
import { Badge, Button, Card, EmptyState, SearchField, SelectField, TextField, TextAreaField } from '../index';
import './Gallery.css';

export function Gallery() {
  const [clicks, setClicks] = useState(0);
  const [search, setSearch] = useState('');
  const [style, setStyle] = useState('All styles');
  return <main className="component-gallery">
    <h1>Design system examples</h1><p className="muted">Development examples only. No brewing data is saved.</p>
    <Card className="content-card" aria-label="Button states"><h2>Buttons</h2>
      <div className="component-gallery__row">
        <Button onClick={() => setClicks(clicks + 1)}>Try primary button</Button>
        <Button variant="secondary" onClick={() => setClicks(0)}>Reset example</Button>
        <Button disabled>Disabled example</Button><Button busy>Saving…</Button>
      </div><output aria-label="Example count">{clicks}</output>
    </Card>
    <Card className="content-card" aria-label="Text entry states"><h2>Text entry</h2>
      <TextField label="Example recipe name" hint="Optional draft name" />
      <TextField label="Name with error" defaultValue="?" error="Review this name." />
      <TextField label="Disabled name" disabled defaultValue="Unavailable" />
      <TextAreaField label="Example description" hint="Keep notes with the draft." />
      <TextAreaField label="Description with error" error="Review this description." />
      <TextAreaField label="Disabled description" disabled />
    </Card>
    <Card className="content-card" aria-label="Form control states"><h2>Search and select</h2>
      <SearchField label="Find an ingredient" value={search} onChange={(event) => setSearch(event.target.value)} />
      <output aria-label="Search value">{search || 'Nothing entered'}</output>
      <SelectField label="Beer style" value={style} onChange={(event) => setStyle(event.target.value)}>
        <option>All styles</option><option>Custom</option>
      </SelectField><output aria-label="Selected style">{style}</output>
      <SearchField label="Search with error" defaultValue="?" aria-invalid="true" aria-describedby="example-error" />
      <p className="field-error" id="example-error">Enter an ingredient name.</p>
    </Card>
    <Card clip aria-label="Empty state example"><EmptyState badge="Example" title="A reusable empty state" description="Use shared presentation with screen-specific content."><Badge>Neutral badge</Badge></EmptyState></Card>
  </main>;
}
