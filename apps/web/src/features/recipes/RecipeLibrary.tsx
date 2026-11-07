import {
  Button, Card, CardFooter, EmptyState, IconList, IconTile, InlineNote,
  PageHeading, SearchField, SelectField,
} from '@brewery/ui';
import { Icon } from '@brewery/design-system/icons';
import './RecipeLibrary.css';

export function RecipeLibrary() {
  return <>
    <PageHeading eyebrow="A little planning. A better brew." title="Recipe library"
      description="A home for your recipes, experiments, and next great batch."
      action={<Button disabled aria-describedby="recipe-availability"><Icon name="plus" />New recipe</Button>} />

    <div className="library-layout">
      <Card clip aria-label="Recipe library preview">
        <div className="form-toolbar">
          <SearchField label="Search recipes" placeholder="Search recipes…" disabled aria-describedby="recipe-availability" />
          <SelectField label="Filter by style" disabled aria-describedby="recipe-availability"><option>All styles</option></SelectField>
        </div>
        <EmptyState badge="Room for something good"
          title={<>Every good batch starts<br className="desktop-break" /> with a recipe.</>}
          description={<>From a well-loved pale ale to your next experiment,<br className="desktop-break" /> keep the details that make it yours.</>}>
          <p id="recipe-availability">Recipe creation, search, and filtering are coming in a future update. No recipes have been loaded.</p>
        </EmptyState>
        <CardFooter icon="lock">Your brewing records belong on your home network.</CardFooter>
      </Card>

      <aside aria-label="Recipe planning guidance">
        <Card className="content-card">
          <IconTile name="leaf" />
          <p className="eyebrow">Keep the inspiration</p>
          <h2>Good recipes have a story.</h2>
          <p className="muted small">When recipe saving is available, keep the source alongside your ingredients and steps.</p>
          <IconList items={[
            { icon: 'sprout', title: 'Your own creations', description: 'Ideas, adjustments, and happy accidents.' },
            { icon: 'book', title: 'From the bookshelf', description: 'Remember the author, title, and page.' },
            { icon: 'link', title: 'Found along the way', description: 'Keep a website link and your notes.' },
          ]} />
        </Card>
        <InlineNote icon="shield">Advice for your brew.<br /><strong>You’re always in control.</strong></InlineNote>
      </aside>
    </div>

    <section className="journey" aria-labelledby="journey-title">
      <div className="journey__heading"><p className="eyebrow">Built around your brew day</p><h2 id="journey-title">Plan. Brew. Learn.</h2></div>
      <IconList boxed className="journey__steps" items={[
        { icon: 'clipboard', title: 'Make a plan', description: 'Ingredients, targets, and every step.' },
        { icon: 'flask', title: 'Be in the moment', description: 'A guide for the day, at your pace.' },
        { icon: 'sprout', title: 'Make the next one better', description: 'Bring your notes back to the recipe.' },
      ]} />
    </section>
  </>;
}
