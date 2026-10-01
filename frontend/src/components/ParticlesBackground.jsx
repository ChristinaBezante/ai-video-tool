import { useMemo } from 'react';
import { Particles, ParticlesProvider } from '@tsparticles/react';
import { loadSlim } from '@tsparticles/slim';

// Must be a stable reference across renders (ParticlesProvider requirement).
const initEngine = async (engine) => {
  await loadSlim(engine);
};

export default function ParticlesBackground({ id = 'particles-js' }) {
  const options = useMemo(() => ({
    fullScreen: { enable: false },
    background: { color: { value: 'transparent' } },
    fpsLimit: 60,
    particles: {
      number: { value: 60, density: { enable: true, area: 900 } },
      color: { value: ['#7c3aed', '#ff3b9a', '#ffffff'] },
      shape: { type: 'circle' },
      opacity: { value: { min: 0.15, max: 0.5 } },
      size: { value: { min: 1, max: 3 } },
      links: {
        enable: true,
        distance: 140,
        color: '#7c3aed',
        opacity: 0.25,
        width: 1,
      },
      move: {
        enable: true,
        speed: 1.2,
        direction: 'none',
        random: true,
        straight: false,
        outModes: { default: 'out' },
      },
    },
    interactivity: {
      events: {
        onHover: { enable: true, mode: 'grab' },
        resize: { enable: true },
      },
      modes: {
        grab: { distance: 160, links: { opacity: 0.5 } },
      },
    },
    detectRetina: true,
  }), []);

  return (
    <ParticlesProvider init={initEngine}>
      <Particles id={id} className="particles-background" options={options} />
    </ParticlesProvider>
  );
}


