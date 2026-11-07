import { createRoot } from 'react-dom/client';
import { Gallery } from '@brewery/ui/examples';
import '@brewery/design-system/styles.css';
import '@brewery/ui/styles.css';

createRoot(document.getElementById('root')!).render(<Gallery />);
