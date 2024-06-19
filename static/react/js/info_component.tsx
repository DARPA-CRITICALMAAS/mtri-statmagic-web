import { createRoot } from 'react-dom/client';
import 'vite/modulepreload-polyfill'
import InfoModal from './modal.tsx';

const domNode: HTMLElement = document.getElementById('info-button')!;
const root = createRoot(domNode);
root.render(<InfoModal />)
