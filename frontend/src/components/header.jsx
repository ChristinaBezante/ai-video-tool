import '../styles/header.css';
import { Play } from 'lucide-react';
import { useRef } from 'react';
import gsap from 'gsap';

export default function Header() {
  const getStartedRef = useRef(null);

  const handleGetStartedHover = (e) => {
    gsap.to(e.currentTarget, {
      x: 4,
      duration: 0.3,
      ease: 'power2.out',
    });
    gsap.to(e.currentTarget.querySelector('.arrow'), {
      x: 3,
      duration: 0.3,
      ease: 'power2.out',
    });
  };

  const handleGetStartedHoverOut = (e) => {
    gsap.to(e.currentTarget, {
      x: 0,
      duration: 0.3,
      ease: 'power2.out',
    });
    gsap.to(e.currentTarget.querySelector('.arrow'), {
      x: 0,
      duration: 0.3,
      ease: 'power2.out',
    });
  };

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
          <a
            href="/#features"
            className="nav-link"
            onMouseEnter={(e) => {
              const underline = e.target.querySelector('.nav-underline');
              if (underline) {
                gsap.to(underline, {
                  width: '100%',
                  duration: 0.4,
                  ease: 'power2.out',
                });
              }
            }}
            onMouseLeave={(e) => {
              const underline = e.target.querySelector('.nav-underline');
              if (underline) {
                gsap.to(underline, {
                  width: '0%',
                  duration: 0.3,
                  ease: 'power2.inOut',
                });
              }
            }}
          >
            Discover
            <span className="nav-underline"></span>
          </a>
          <a
            href="/#about"
            className="nav-link"
            onMouseEnter={(e) => {
              const underline = e.target.querySelector('.nav-underline');
              if (underline) {
                gsap.to(underline, {
                  width: '100%',
                  duration: 0.4,
                  ease: 'power2.out',
                });
              }
            }}
            onMouseLeave={(e) => {
              const underline = e.target.querySelector('.nav-underline');
              if (underline) {
                gsap.to(underline, {
                  width: '0%',
                  duration: 0.3,
                  ease: 'power2.inOut',
                });
              }
            }}
          >
            About Us
            <span className="nav-underline"></span>
          </a>
          <a
            href="/upload"
            className="nav-link get-started-link"
            ref={getStartedRef}
            onMouseEnter={handleGetStartedHover}
            onMouseLeave={handleGetStartedHoverOut}
          >
            Get Started
            <span className="arrow">→</span>
          </a>
        </nav>
      </div>
    </header>
  );
}