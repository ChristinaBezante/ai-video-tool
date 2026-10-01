import '../styles/header.css';
import { ArrowUpRight, Play } from 'lucide-react';
import CommandPalette from './CommandPalette';

const NAV_LINKS = [
  { href: '/#features', label: '01 discover' },
  { href: '/#about', label: '02 about' },
];

export default function Header() {
  return (
    <header className="main-header">
      <a href="/" className="logo-link">
        <div className="logo-icon">
          <Play className="logo-icon-svg" />
        </div>
        <span className="logo-label">Ctrl + Vid</span>
      </a>

      {NAV_LINKS.map((link) => (
        <a key={link.href} href={link.href} className="cell nav-link">
          {link.label}
        </a>
      ))}

      <div className="spacer" />

      <CommandPalette />

      <a href="/upload" className="cta">
        try now
        <ArrowUpRight />
      </a>
    </header>
  );
}