import { useEffect, useRef, useSyncExternalStore } from 'react';
import { useService } from '../api/useService';
import type { ServiceState } from '@brewery/communications';
import { Badge, Button, Card, PageHeading } from '@brewery/ui';
import { Icon } from '@brewery/design-system/icons';
import { RecipeLibrary } from '../features/recipes/RecipeLibrary';
import './App.css';

function subscribe(callback: () => void) {
  window.addEventListener('hashchange', callback);
  return () => window.removeEventListener('hashchange', callback);
}
function routeSnapshot() { return window.location.hash || '#/recipes'; }

function Connection({ state, retry }: { state: ServiceState; retry: () => void }) {
  const checking = state === 'checking';
  const ready = state === 'ready';
  return <section className={`connection connection--${state}`} aria-label="Brewing service connection" aria-busy={checking}>
    <div className="connection__message" role="status">
      <Icon name={ready ? 'check' : checking ? 'refresh' : 'offline'} />
      <div><strong>{ready ? 'Brewing service ready' : checking ? 'Checking brewing service…' : 'Brewing service unavailable'}</strong>
        {!ready && <p>{checking ? 'Waiting for a response from your home brewery.' : 'The service could not be reached or is not ready. You can still explore this preview.'}</p>}
      </div>
    </div>
    <Button variant="secondary" busy={checking} onClick={retry} aria-label={checking ? 'Checking connection' : 'Check connection again'}>
      <Icon name="refresh" />{checking ? 'Checking…' : 'Check again'}
    </Button>
  </section>;
}

function Home() {
  return <>
    <PageHeading eyebrow="Your home brewery" title="More good brewing ahead." description="A little preparation, a clear brew day, and room to learn from every batch." />
    <Card className="content-card"><Badge tone="positive">An early look</Badge><h2>Start with the recipe.</h2><p className="muted">Explore the recipe library preview. Recipe saving and guided brew days will be added in future updates.</p><a href="#/recipes" className="text-link">Open recipe library<Icon name="arrow" /></a></Card>
  </>;
}

function Settings() {
  return <>
    <PageHeading eyebrow="Simple by design" title="Settings" description="A companion that stays close to your brewery." />
    <Card className="content-card"><h2>About this companion</h2><dl className="definition-list">
      <div><dt>Local brewing</dt><dd>Your browser connects to the brewing service on your home network. No cloud account is required for this preview.</dd></div>
      <div><dt>You operate the equipment</dt><dd>The app is here to monitor, record, and advise. Physical actions always stay with you.</dd></div>
      <div><dt>What is available today</dt><dd>Navigation, the recipe library preview, and service connection checks. Recipe storage, imports, batches, and sensors are not available yet.</dd></div>
    </dl></Card>
  </>;
}

function NotFound() {
  return <Card className="content-card"><h1 id="page-title" tabIndex={-1}>Page not found</h1><p className="muted">That page isn’t part of your brewing companion yet.</p><a className="text-link" href="#/recipes">Back to recipes<Icon name="arrow" /></a></Card>;
}

const titles: Record<string, string> = { '#/recipes': 'Recipe library', '#/home': 'Home', '#/settings': 'Settings' };

export function App() {
  const route = useSyncExternalStore(subscribe, routeSnapshot);
  const previousRoute = useRef(route);
  const service = useService();
  useEffect(() => {
    document.title = `${titles[route] ?? 'Page not found'} · Homebrew`;
    if (previousRoute.current !== route) document.getElementById('page-title')?.focus();
    previousRoute.current = route;
  }, [route]);

  return <>
    <a className="skip-link" href="#main-content" onClick={(event) => {
      event.preventDefault(); document.getElementById('main-content')?.focus();
    }}>Skip to content</a>
    <header className="app-header">
      <div className="app-header__inner">
        <a href="#/home" className="brand" aria-label="Homebrew home"><span className="brand__mark"><Icon name="wheat" /></span><span><strong>Homebrew</strong><small>YOUR BREWING COMPANION</small></span></a>
        <Badge tone="positive"><Icon name="home" />Local companion</Badge>
      </div>
      <nav className="navigation" aria-label="Main navigation"><div className="navigation__inner">
        <a href="#/home" aria-current={route === '#/home' ? 'page' : undefined}><Icon name="home" />Home</a>
        <a href="#/recipes" aria-current={route === '#/recipes' ? 'page' : undefined}><Icon name="book" />Recipes</a>
        <span aria-disabled="true" title="Brew days are not available yet"><Icon name="flask" />Brew day</span>
        <span aria-disabled="true" title="Batch history is not available yet"><Icon name="clipboard" />Batches</span>
        <a href="#/settings" aria-current={route === '#/settings' ? 'page' : undefined}><Icon name="settings" />Settings</a>
      </div></nav>
    </header>
    <main id="main-content" tabIndex={-1} className="app-main">
      <Connection {...service} />
      {route === '#/recipes' ? <RecipeLibrary /> : route === '#/home' ? <Home /> : route === '#/settings' ? <Settings /> : <NotFound />}
    </main>
    <footer className="app-footer"><span><Icon name="wheat" />Made for the way you brew.</span><span>Plan thoughtfully. Brew manually. Keep learning.</span></footer>
  </>;
}
