import { createRoot } from 'react-dom/client';
import 'vite/modulepreload-polyfill'
import InfoButton from './InfoButtonComponent.tsx';

const domNode: HTMLElement = document.getElementById('info-button')!;
const root = createRoot(domNode);
root.render(<InfoButton />)
