import '../styles/header.css';
import { Play } from 'lucide-react';

export default function Header() {
  return (
    <header className="main-header">
      <div className="header-container">
        <a href="/" className="logo-link">
          <div className="logo-icon">
            <Play className="logo-icon-svg" />
          </div>
          <span className="logo-label">Ctrl + Vid</span>
        </a>
        <nav className="main-nav">
          <a href="/#features" className="nav-link">Discover</a>
          <a href="/#about" className="nav-link">About Us</a>
          <a href="/upload" className="btn btn-primary">Get Started</a>
        </nav>
      </div>
    </header>
  );
}