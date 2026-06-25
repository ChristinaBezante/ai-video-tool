import "../styles/footer.css"
import { Play, Aperture } from 'lucide-react';

const Footer = () => {
  return (
    <div className='footer-container'>
      <div className='footer'>
        <div className='footer-up'>
          <div className='footer-brand'>
            <a href='/' className='footer-logo-link'>
              <div className='footer-logo-square'>
                <Play className='footer-logo-svg' />
              </div>
              <div>
                <span className='footer-logo-label'>Ctrl + Vid</span>
                <p className='footer-tagline'>Make video insight feel effortless for every team.</p>
              </div>
            </a>
            <div className='footer-social-block'>
              <span className='footer-social-title'>Follow us</span>
              <div className='footer-social-links'>
                <div className='footer-social-icon'><Aperture size={18} /></div>
                <div className='footer-social-icon'><Aperture size={18} /></div>
                <div className='footer-social-icon'><Aperture size={18} /></div>
              </div>
            </div>
          </div>

          <div className='footer-link-columns'>
            <div className='footer-column'>
              <h4>Explore</h4>
              <a href='#features'>Features</a>
              <a href='#about'>About Us</a>
              <a href='#get-started'>Get Started</a>
            </div>
            <div className='footer-column'>
              <h4>Company</h4>
              <a href='#'>Privacy</a>
              <a href='#'>Terms</a>
              <a href='#'>Contact</a>
            </div>
          </div>
        </div>

        <div className='footer-down'>
          <p className='footer-bottom-text'>© 2026 Ctrl + Vid. All rights reserved.</p>
          <div className='footer-legal-links'>
            <a className='footer-legal-link' href='#'>Privacy</a>
            <a className='footer-legal-link' href='#'>Terms</a>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Footer