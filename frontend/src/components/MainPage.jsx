import Header from './header.jsx'
import Footer from './Footer.jsx'
import { useNavigate } from "react-router-dom";

function MainPage() {

  const navigate = useNavigate()

  const navToUpload = () => {
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
              <a className="btn btn-primary" href="#try" onClick={navToUpload}>Try Now</a>
              <a className="btn btn-secondary" href="#features">Learn</a>
            </div>
          </div>
          <div className="hero-visual">
            <div className="hero-card" />
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
            <a className="btn btn-primary btn-card-cta" href="#get-started">Start Analysis</a>
          </div>
        </div>
      </section>

      <section id="about" className="about-section">
        <div className="about-section-inner">
          <div className="about-grid">
            <div className="about-copy">
              <p className="eyebrow">About Us</p>
              <h2>Video intelligence designed for teams that need clarity and speed.</h2>
              <p>
                Ctrl + Vid turns raw footage into searchable insights with fast analysis,
                polished summaries, and a modern interface built for visual workflows.
              </p>
              <div className="about-highlights">
                <article className="about-highlight">
                  <span className="about-highlight-icon">⚡</span>
                  <div>
                    <h3>Faster decisions</h3>
                    <p>See key moments and trends immediately, without digging through raw footage.</p>
                  </div>
                </article>
                <article className="about-highlight">
                  <span className="about-highlight-icon">🔍</span>
                  <div>
                    <h3>Actionable insight</h3>
                    <p>We surface the best information so your team can move with confidence.</p>
                  </div>
                </article>
              </div>
            </div>
            <div className="about-card">
              <span className="about-tag">Built for video teams</span>
              <h3>From capture to insight, every step feels faster and smarter.</h3>
              <p>
                Clean summaries, insightful dashboards, and secure collaboration tools make video data
                valuable and easy to act on across your whole team.
              </p>
              <div className="about-feature-list">
                <span className="about-feature-pill">Automated scene tagging</span>
                <span className="about-feature-pill">Insight dashboards</span>
                <span className="about-feature-pill">Secure collaboration</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}

export default MainPage
