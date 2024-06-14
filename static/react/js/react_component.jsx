import { createRoot } from 'react-dom/client';
import 'vite/modulepreload-polyfill'

function TestItem({ value }) {
    return (
        <div className="collapse react">
            <div className="header topbar react"><span className="collapse">+ </span>
                {value}
            </div>
        </div>
    )
}

function TestComponent() {
    // return <p>Hello from React!</p>;

    return (
        <div className="collapse react">
            <div className="header topbar react"><span className="collapse">+ </span>
                Dynamically inserted using React/Vite
            </div>
        </div>
    )
}

const rows = [];
rows.push(<TestComponent />);
for (let i = 0; i < 4; i++) {
    rows.push(<TestItem value={i}/>);
}

const domNode = document.getElementById('react');
const root = createRoot(domNode);
// root.render(<p>Hello from React+Vite</p>);
// root.render(<TestComponent />)
root.render(rows)