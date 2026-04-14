import '../styles/header.css';
import logo from '../icons/logo.png';

export default function Header() {
  return (
    <header className="main-header">
      <div className="header-container">
        
        <a href="/" className="logo-link">
          <img src={logo} alt="Ctrl+Vid" className="brand-logo" />
        </a>
        <nav className="main-nav">
          <a href="#discover" className="nav-link">Discover</a>
          <a href="#about" className="nav-link">About Us</a>
          <a href="#get-started" className="btn btn-primary">Get Started</a>
        </nav>
        
      </div>
    </header>
  );
}