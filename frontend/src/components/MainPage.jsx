import Header from './header.jsx'
import Footer from './Footer.jsx'
import { useEffect, useRef, useState } from 'react';
import { Zap, Shield, Users, Star } from 'lucide-react';
import { useLocation, useNavigate } from "react-router-dom";

function MainPage() {

  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (!location.hash) {
      return;
    }

    const targetId = location.hash.replace('#', '');
    const target = document.getElementById(targetId);
    if (!target) {
      return;
    }

    requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }, [location.hash]);

  const heroWords = ['reveal', 'understand', 'unlock', 'transform'];
  const [wordIdx, setWordIdx] = useState(0);
  const [wordVisible, setWordVisible] = useState(true);

  useEffect(() => {
    const id = setInterval(() => {
      setWordVisible(false);
      setTimeout(() => {
        setWordIdx(i => (i + 1) % heroWords.length);
        setWordVisible(true);
      }, 380);
    }, 2600);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const els = document.querySelectorAll('.reveal');
    const obs = new IntersectionObserver(
      entries => entries.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add('reveal-visible'); obs.unobserve(e.target); }
      }),
      { threshold: 0.14 }
    );
    els.forEach(el => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  const heroRef = useRef(null);
  const labelRef = useRef(null);
  const trackRef = useRef(null);
  const scrubFillRef = useRef(null);
  const playheadRef = useRef(null);
  const typeRef = useRef(null);
  const cursorRef = useRef(null);
  const stepFillRef = useRef(null);
  const [tsReady, setTsReady] = useState(false);

  // rAF-based scroll progress — reads from the actual scroll container
  useEffect(() => {
    let rafId;
    const update = () => {
      const fill = stepFillRef.current;
      if (fill) {
        const trackH = fill.parentElement?.offsetHeight || 0;
        // #root has overflow-x:hidden which forces overflow-y:auto,
        // making it the real scroll container instead of window
        const root = document.getElementById('root');
        const scrollTop = (root && root.scrollTop)
          || document.body.scrollTop
          || document.documentElement.scrollTop
          || window.scrollY
          || 0;
        const scrollEl = (root && root.scrollTop) ? root
          : (document.body.scrollTop ? document.body : document.documentElement);
        const totalH = Math.max(
          scrollEl.scrollHeight - scrollEl.clientHeight,
          1
        );
        fill.style.height = `${Math.min(1, scrollTop / totalH) * trackH}px`;
      }
      rafId = requestAnimationFrame(update);
    };
    rafId = requestAnimationFrame(update);
    return () => cancelAnimationFrame(rafId);
  }, []);

  const typeText = 'Ctrl + Vid transforms how you understand visual content. Discover patterns, extract meaning and unlock insights from video data like never before.';

  useEffect(() => {
    const el = typeRef.current;
    const cursor = cursorRef.current;
    if (!el || !cursor) return;
    el.textContent = '';
    let i = 0;
    let startTimer = setTimeout(() => {
      const tick = setInterval(() => {
        el.textContent = typeText.slice(0, ++i);
        if (i >= typeText.length) {
          clearInterval(tick);
          setTimeout(() => {
            if (cursor) cursor.classList.add('type-cursor-done');
          }, 1800);
        }
      }, 26);
      return () => clearInterval(tick);
    }, 700);
    return () => clearTimeout(startTimer);
  }, []);

  const totalSecs = 3600;

  const scrubTicks = [
    { label: '0:00',    pct: 0          },
    { label: '0:10:00', pct: 100 / 6    },
    { label: '0:20:00', pct: 200 / 6    },
    { label: '0:30:00', pct: 50         },
    { label: '0:40:00', pct: 400 / 6    },
    { label: '0:50:00', pct: 500 / 6    },
    { label: '1:00:00', pct: 100        },
  ];

  const handleHeroMouseMove = (e) => {
    const trackRect = trackRef.current?.getBoundingClientRect();
    if (!trackRect) return;
    const rawX = e.clientX - trackRect.left;
    const progress = Math.max(0, Math.min(1, rawX / trackRect.width));
    const pct = `${progress * 100}%`;
    if (scrubFillRef.current)  scrubFillRef.current.style.width = pct;
    if (playheadRef.current)   playheadRef.current.style.left  = pct;
    if (!tsReady) setTsReady(true);
    const secs = Math.floor(progress * totalSecs);
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    if (labelRef.current) {
      labelRef.current.textContent = h > 0 ? `${h}:${m}:${s}` : `${m}:${s}`;
    }
  };

  const navToUpload = (event) => {
    event.preventDefault()
    navigate("/upload")
  }

  return (
    <div className="page-content-wrap">
      <div className="page-bar-track" aria-hidden="true">
        <div ref={stepFillRef} className="page-bar-fill" />
        <div className="page-stepper-node psn-1" />
        <div className="page-stepper-node psn-2" />
        <div className="page-stepper-node psn-3" />
      </div>
      <main className="main-hero" ref={heroRef} onMouseMove={handleHeroMouseMove}>
        <div className="hero-orb hero-orb-1" />
        <div className="hero-orb hero-orb-2" />
        <div className="hero-orb hero-orb-3" />
        <div className={`hero-scrubber${tsReady ? ' hero-scrubber-active' : ''}`}>
          <div className="hero-scrubber-labels">
            {scrubTicks.map(({ label, pct }) => (
              <span key={label} className="hero-scrubber-label" style={{ left: `${pct}%` }}>{label}</span>
            ))}
          </div>
          <div ref={trackRef} className="hero-scrubber-track">
            <div ref={scrubFillRef} className="hero-scrubber-fill" />
            <div ref={playheadRef} className="hero-scrubber-playhead">
              <div className="hero-ts-badge">
                <span ref={labelRef} className="hero-ts-label">0:00</span>
              </div>
              <div className="hero-scrubber-dot" />
            </div>
          </div>
        </div>
        <section className="hero-panel">
          <div className="hero-copy">
            <h1>
              See what video<br />
              analysis <span className="hero-gradient">can</span><br />
              <span className={`hero-gradient hero-word${wordVisible ? '' : ' hero-word-out'}`}>
                {heroWords[wordIdx]}
              </span>
            </h1>
            <p>
              <span ref={typeRef} /><span ref={cursorRef} className="type-cursor">|</span>
            </p>
            <div className="hero-actions">
              <a className="btn btn-primary" href="/upload" onClick={navToUpload}>Try Now</a>
              <a className="btn btn-secondary" href="#features">Learn</a>
            </div>
          </div>
          <div className="hero-visual">
            <div className="hero-float-wrapper">
              <div className="hero-glow-orb"></div>
              <img
                src="/uploads/scissors-cutting.png"
                alt="Scissors cutting video frame"
                className="hero-float-image"
              />
              <div className="hero-glow-ground"></div>
            </div>
          </div>
        </section>
      </main>

      <section id="features" className="main-transition">
        <div className="main-transition-inner">
          <div className="feature-head reveal">
            <h2>
              Follow these <span className="feature-heading-accent">simple steps</span> to get started
            </h2>
          </div>
          <div className="feature-grid">
            <article className="feature-card feature-card-1 reveal reveal-delay-1">
              <div className="feature-number">01</div>
              <div className="feature-icon">↑</div>
              <h3>Upload Video</h3>
              <p>Select and upload your video file to begin the analysis process.</p>
            </article>
            <article className="feature-card feature-card-2 reveal reveal-delay-2">
              <div className="feature-number">02</div>
              <div className="feature-icon">★</div>
              <h3>Analyze Content</h3>
              <p>Our AI processes your video content and extracts key information.</p>
            </article>
            <article className="feature-card feature-card-3 reveal reveal-delay-3">
              <div className="feature-number">03</div>
              <div className="feature-icon">↓</div>
              <h3>Retrieve Results</h3>
              <p>Access your analyzed data and insights in an easy-to-use format.</p>
            </article>
          </div>
          <div className="feature-cta">
            <a className="btn btn-primary btn-card-cta" href="/upload" onClick={navToUpload}>Start Analysis</a>
          </div>
        </div>
      </section>

      <section id="about" className="about-section">
        <div className="about-section-inner">
          <div className="about-grid about-grid-compact">
            <div className="about-copy reveal">
              <h2>
                About <span className="feature-heading-accent">Us</span>
              </h2>
              <p>
                Ctrl + Vid combines speed, clarity, and privacy into a video workflow that feels
                effortless and consistent with the rest of the site. We built it for teams who are
                tired of scrubbing through footage, and for creators who want their video data to be
                immediately useful, not just stored.
              </p>
              <p>
                Every part of the experience is designed to make video easier to explore, share,
                and act on from quick searchable clips to secure collaboration and instant
                visual summaries.
              </p>
              <div className="about-feature-list about-feature-list-compact">
                <span className="about-feature-pill">Searchable clips</span>
                <span className="about-feature-pill">Auto summaries</span>
                <span className="about-feature-pill">Team-friendly</span>
              </div>
              <div className="about-team-cards">
                <article className="team-card about-team-card">
                  <div className="team-avatar">CB</div>
                  <div>
                    <h3>Christina - Ioanna Bezante</h3>
                    <p className="team-role">Co-founder</p>
                  </div>
                </article>
                <article className="team-card about-team-card">
                  <div className="team-avatar">EG</div>
                  <div>
                    <h3>Enterisa Gjozi</h3>
                    <p className="team-role">Co-founder</p>
                  </div>
                </article>
              </div>
            </div>
            <div className="about-card about-values-card reveal reveal-delay-2">
              <p className="about-values-eyebrow">Core values</p>
              <div className="about-values-stack">
                <article className="about-value-row">
                  <span className="about-value-rail" aria-hidden="true">
                    <span className="about-value-dot" />
                  </span>
                  <div className="about-value-content">
                    <span className="about-value-kicker">01</span>
                    <div className="about-value-heading">
                      <Zap className="about-value-svg" />
                      <h3>Speed first</h3>
                    </div>
                    <p>Quick analysis and instant access keep the workflow moving.</p>
                  </div>
                </article>

                <article className="about-value-row">
                  <span className="about-value-rail" aria-hidden="true">
                    <span className="about-value-dot" />
                  </span>
                  <div className="about-value-content">
                    <span className="about-value-kicker">02</span>
                    <div className="about-value-heading">
                      <Shield className="about-value-svg" />
                      <h3>Your content, your control</h3>
                    </div>
                    <p>Secure processing and private uploads make the product feel trustworthy.</p>
                  </div>
                </article>

                <article className="about-value-row about-value-row-highlight">
                  <span className="about-value-rail" aria-hidden="true">
                    <span className="about-value-dot" />
                  </span>
                  <div className="about-value-content">
                    <span className="about-value-kicker">03</span>
                    <div className="about-value-heading">
                      <Users className="about-value-svg" />
                      <h3>Built for teams</h3>
                    </div>
                    <p>Designed to work equally well for solo creators and larger video teams.</p>
                  </div>
                </article>
              </div>
            </div>
          </div>
        </div>
      </section>

    </div>
  )
}

export default MainPage
