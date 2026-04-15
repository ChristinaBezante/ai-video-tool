import "../styles/footer.css"
import logo from '../icons/logo.png'
import { Aperture } from 'lucide-react';

const Footer = () => {
  

  return (
    <div className='footer-container'>
      <div className='footer'>
        <div className='footer-up'>
          <div className='footer-logoicon-social'>
            <div className='footer-logoicon'>
              <img src={logo} alt="Logo" />
            </div>
            <div className='footer-social'>
              <div className="social-logos">
                <div className="footer-icons" style={{color: 'var(--text)'}}><Aperture /></div>
                <div className="footer-icons" style={{color: 'var(--text)'}}><Aperture /></div>
                <div className="footer-icons" style={{color: 'var(--text)'}}><Aperture /></div>
              </div>
            </div>
          </div>

          <div className='footer-logo-links'>
            <div className='footer-logo'>
              <h2 style={{color: 'var(--text-h)'}}>Write logo here whatever</h2>
            </div>
            <div className='footer-links'>
              <div className='footer-links-one'>
                <a href="">Link 1</a>
                <a href="">Link 2</a>
                <a href="">Link 3</a>
              </div>
              <div className='footer-links-one'>
                <a href="">Link 1</a>
                <a href="">Link 2</a>
                <a href="">Link 3</a>
              </div>
              <div className='footer-links-one'>
                <a href="">Link 1</a>
                <a href="">Link 2</a>
                <a href="">Link 3</a>
              </div>
            </div>
          </div>
        </div>

        <div className='footer-down'>
          <div className="footer-copyright">
            <p style={{color: 'var(--text-h)', fontSize: '12px'}}>Copyright 2024. All rights reserved.</p>
          </div>
        </div>

      </div>
    </div>
  )


}

export default Footer