import Header from './header.jsx'
import Footer from './Footer.jsx'
import { useEffect } from 'react';
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

  const navToUpload = (event) => {
    event.preventDefault()
    navigate("/upload")
  }

  return (
    <>
      <main className="main-hero">
        <section className="hero-panel">
          <div className="hero-copy">
            <h1>
              See what video<br />
              analysis <span className="hero-gradient">can</span><br />
              <span className="hero-gradient">reveal</span>
            </h1>
            <p>
              Ctrl + Vid transforms how you understand visual content.
              Discover patterns, extract meaning and unlock insights from
              video data like never before.
            </p>
            <div className="hero-actions">
              <a className="btn btn-primary" href="/upload" onClick={navToUpload}>Try Now</a>
              <a className="btn btn-secondary" href="#features">Learn</a>
            </div>
          </div>
          <div className="hero-visual">
            <div className="hero-card">
              <img
                src="/uploads/scissors-cutting.png"
                alt="Scissors cutting video frame"
                className="hero-card-image"
              />
            </div>
          </div>
        </section>
      </main>

      <section id="features" className="main-transition">
        <div className="main-transition-inner">
          <div className="feature-head">
            <h2>
              Follow these <span className="feature-heading-accent">simple steps</span> to get started
            </h2>
          </div>
          <div className="feature-grid">
            <article className="feature-card feature-card-1">
              <div className="feature-number">01</div>
              <div className="feature-icon">↑</div>
              <h3>Upload Video</h3>
              <p>Select and upload your video file to begin the analysis process.</p>
            </article>
            <article className="feature-card feature-card-2">
              <div className="feature-number">02</div>
              <div className="feature-icon">★</div>
              <h3>Analyze Content</h3>
              <p>Our AI processes your video content and extracts key information.</p>
            </article>
            <article className="feature-card feature-card-3">
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
            <div className="about-copy">
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
                and act on — from quick searchable clips to secure collaboration and instant
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
            <div className="about-card about-values-card">
              <article className="about-value-card">
                <div className="about-value-icon">
                  <Zap className="about-value-svg" />
                </div>
                <div>
                  <h3>Speed first</h3>
                  <p>Quick analysis and instant access keep the workflow moving.</p>
                </div>
              </article>
              <article className="about-value-card">
                <div className="about-value-icon">
                  <Shield className="about-value-svg" />
                </div>
                <div>
                  <h3>Your content, your control</h3>
                  <p>Secure processing and private uploads make the product feel trustworthy.</p>
                </div>
              </article>
              <article className="about-value-card">
                <div className="about-value-icon">
                  <Users className="about-value-svg" />
                </div>
                <div>
                  <h3>Built for teams</h3>
                  <p>Designed to work equally well for solo creators and larger video teams.</p>
                </div>
              </article>
            </div>
          </div>
        </div>
      </section>

    </>
  )
}

export default MainPage
