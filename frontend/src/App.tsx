import { SkillDashboard } from './components/SkillDashboard';
import './styles.css';

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Beacon Lab</h1>
        <p className="subtitle">AI &amp; Machine Learning — agent skill discovery &amp; validation</p>
      </header>
      <main>
        <SkillDashboard />
      </main>
      <footer className="app-footer">
        <p>Beacon Lab · Ryan Vo · <a href="mailto:ryandtvo@gmail.com">ryandtvo@gmail.com</a></p>
      </footer>
    </div>
  );
}

export default App;