import Header from './header.jsx'
import Footer from './Footer.jsx'
import ParticlesBackground from './ParticlesBackground.jsx';
import { useEffect, useRef, useState } from 'react';
import { Star } from 'lucide-react';
import { useLocation, useNavigate } from "react-router-dom";

const demoQueries = [
  { q: 'what did she say about recursion?', ts: '12:41', a: '"Recursion is just a function trusting itself to finish the job."' },
  { q: 'where do we set up the venv?', ts: '03:08', a: 'Activate the virtual environment before installing anything.' },
  { q: 'summarize the last 10 minutes', ts: '48:52', a: 'Wraps up error handling, then a live demo of the CLI.' },
];

const insightData = {
  speed:    { label: 'How fast?',      text: 'Ask "what happens at minute 34?" and get an answer before you\'d even find the scrubber. No buffering, no waiting — just the moment you need.' },
  privacy:  { label: 'Your data',      text: 'We never see your videos. Everything runs locally on your machine, so sensitive footage stays exactly where you left it.' },
  students: { label: 'Built for you',  text: 'Whether it\'s one lecture or an entire semester, you can search everything you\'ve recorded and jump straight to the moment that matters.' },
  footage:  { label: 'No more scrubbing', text: 'We built this because we were tired of dragging a timeline slider hoping we\'d land on the right scene. There\'s a better way.' },
};

function InsightSpan({ word, active, onToggle }) {
  return (
    <span
      className={`insight-word${active ? ' insight-word-open' : ''}`}
      role="button"
      tabIndex={0}
      onClick={(e) => { e.stopPropagation(); onToggle(word); }}
      onKeyDown={(e) => e.key === 'Enter' && onToggle(word)}
    >
      {word}
      {active && (
        <span className="insight-tooltip" role="tooltip">
          <span className="insight-tooltip-text">{insightData[word].text}</span>
        </span>
      )}
    </span>
  );
}

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
  const demoQueryRef = useRef(null);
  const demoResultRef = useRef(null);
  const demoTsRef = useRef(null);
  const demoAnswerRef = useRef(null);
  const [tsReady, setTsReady] = useState(false);
  const [activeInsight, setActiveInsight] = useState(null);
  const toggleInsight = (word) => setActiveInsight(prev => prev === word ? null : word);

  useEffect(() => {
    if (!activeInsight) return;
    const close = () => setActiveInsight(null);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [activeInsight]);

  // Show a floating "Back to Top" button once scrolled past the hero.
  // #root is the real scroll container here (see the rAF effect below), so
  // we listen on it instead of window.
  const [showBackToTop, setShowBackToTop] = useState(false);

  useEffect(() => {
    const root = document.getElementById('root');
    const scrollEl = root || document.documentElement;
    const handleScroll = () => {
      const scrollTop = scrollEl.scrollTop || window.scrollY || 0;
      setShowBackToTop(scrollTop > 480);
    };
    scrollEl.addEventListener('scroll', handleScroll, { passive: true });
    return () => scrollEl.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToTop = () => {
    const root = document.getElementById('root');
    const scrollEl = root || document.documentElement;
    scrollEl.scrollTo({ top: 0, behavior: 'smooth' });
  };
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

  // Loops through canned searches in the "about" terminal demo: type a
  // question, reveal the matching timestamp + answer, then erase and repeat.
  useEffect(() => {
    let cancelled = false;
    const timeouts = [];
    const wait = (ms) => new Promise((resolve) => {
      timeouts.push(setTimeout(resolve, ms));
    });

    const typeInto = async (el, text) => {
      el.textContent = '';
      for (let i = 0; i < text.length; i++) {
        if (cancelled) return;
        el.textContent = text.slice(0, i + 1);
        await wait(28);
      }
    };

    const eraseFrom = async (el) => {
      const text = el.textContent;
      for (let i = text.length; i >= 0; i--) {
        if (cancelled) return;
        el.textContent = text.slice(0, i);
        await wait(12);
      }
    };

    const run = async () => {
      let i = 0;
      while (!cancelled) {
        const queryEl = demoQueryRef.current;
        const resultEl = demoResultRef.current;
        const tsEl = demoTsRef.current;
        const answerEl = demoAnswerRef.current;
        if (!queryEl || !resultEl || !tsEl || !answerEl) return;

        const { q, ts, a } = demoQueries[i % demoQueries.length];
        await typeInto(queryEl, q);
        if (cancelled) return;
        await wait(400);
        tsEl.textContent = ts;
        answerEl.textContent = a;
        resultEl.classList.add('about-demo-result-visible');
        await wait(2800);
        if (cancelled) return;
        resultEl.classList.remove('about-demo-result-visible');
        await wait(400);
        await eraseFrom(queryEl);
        await wait(300);
        i++;
      }
    };

    run();
    return () => {
      cancelled = true;
      timeouts.forEach(clearTimeout);
    };
  }, []);

  const navToUpload = (event) => {
    event.preventDefault()
    navigate("/upload")
  }

  return (
    <div className="page-content-wrap">
      <button
        type="button"
        className={`back-to-top${showBackToTop ? ' back-to-top-visible' : ''}`}
        onClick={scrollToTop}
        aria-label="Back to top"
      >
        <span className="back-to-top-label">Back to Top</span>
      </button>
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
        <ParticlesBackground id="features-particles" />
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
        <ParticlesBackground id="about-particles" />
        <div className="about-section-inner">
          <div className="about-head reveal">
            <h2>
              About <span className="feature-heading-accent">Us</span>
            </h2>
          </div>

          <div className="about-layout">
            <div className="about-copy reveal reveal-delay-1">
              <p>
                Re-watching a two-hour lecture just to find one explanation is tedious.
                That's why we built Ctrl + Vid.
              </p>
              <p>
                We're two{' '}
                <InsightSpan word="students" active={activeInsight === 'students'} onToggle={toggleInsight} />{' '}
                who got tired of dragging a scrubber back and forth. Ctrl + Vid lets you search a
                lecture like a document: type what you're looking for and jump straight to the{' '}
                <InsightSpan word="footage" active={activeInsight === 'footage'} onToggle={toggleInsight} />{' '}
                that matches, without giving up{' '}
                <InsightSpan word="speed" active={activeInsight === 'speed'} onToggle={toggleInsight} />{' '}
                or{' '}
                <InsightSpan word="privacy" active={activeInsight === 'privacy'} onToggle={toggleInsight} />.
              </p>
            </div>

            <div className="about-demo reveal reveal-delay-2">
              <div className="about-demo-topbar">
                <span className="about-demo-dot about-demo-dot-r" />
                <span className="about-demo-dot about-demo-dot-y" />
                <span className="about-demo-dot about-demo-dot-g" />
                <span className="about-demo-path">search — ctrl+vid</span>
              </div>
              <div className="about-demo-body">
                <div className="about-demo-line">
                  <span className="about-demo-prompt">&gt;</span>
                  <span ref={demoQueryRef} className="about-demo-query" />
                  <span className="type-cursor about-demo-cursor">|</span>
                </div>
                <div ref={demoResultRef} className="about-demo-result">
                  <span className="about-demo-badge">
                    <span ref={demoTsRef} className="about-demo-ts" />
                  </span>
                  <span ref={demoAnswerRef} className="about-demo-answer" />
                </div>
              </div>
            </div>
          </div>

          <div className="about-founders reveal reveal-delay-3">
            <div className="about-founder-list">
              <div className="about-founder-card">
                <span className="about-founder-avatar">CB</span>
                <span className="about-founder-meta">
                  <span className="about-founder-name">
                    Christina - Ioanna Bezante
                  </span>
                  <span className="about-founder-role">Co-founder</span>
                </span>
              </div>
              <div className="about-founder-card">
                <span className="about-founder-avatar">EG</span>
                <span className="about-founder-meta">
                  <span className="about-founder-name">
                    Enterisa Gjozi
                  </span>
                  <span className="about-founder-role">Co-founder</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

    </div>
  )
}

export default MainPage
