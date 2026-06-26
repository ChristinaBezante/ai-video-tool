import { useEffect, useLayoutEffect, useRef } from 'react';

const SCROLL_THRESHOLD = 10;

function useAutoScroll(active) {
  const scrollContentRef = useRef(null);
  const isDisabled = useRef(false);
  const prevScrollTop = useRef(null);

  useEffect(() => {
    const resizeObserver = new ResizeObserver(() => {
      const container = scrollContentRef.current;
      if (!container) {
        return;
      }

      const { scrollHeight, clientHeight, scrollTop } = container;
      if (!isDisabled.current && scrollHeight - clientHeight > scrollTop) {
        container.scrollTo({
          top: scrollHeight - clientHeight,
          behavior: 'smooth'
        });
      }
    });

    if (scrollContentRef.current) {
      resizeObserver.observe(scrollContentRef.current);
    }
    
    return () => resizeObserver.disconnect();
  }, []);

  useLayoutEffect(() => {
    if (!active) {
      isDisabled.current = true;
      return;
    }

    function onScroll() {
      const container = scrollContentRef.current;
      if (!container) {
        return;
      }

      const { scrollHeight, clientHeight, scrollTop } = container;
      if (
        !isDisabled.current &&
        scrollTop < prevScrollTop.current &&
        scrollHeight - clientHeight > scrollTop + SCROLL_THRESHOLD
      ) {
        isDisabled.current = true;
      } else if (
        isDisabled.current &&
        scrollHeight - clientHeight <= scrollTop + SCROLL_THRESHOLD
      ) {
        isDisabled.current = false;
      }
      prevScrollTop.current = scrollTop;
    }

    const container = scrollContentRef.current;
    if (!container) {
      return;
    }

    isDisabled.current = false;
    prevScrollTop.current = container.scrollTop;
    container.addEventListener('scroll', onScroll);

    return () => container.removeEventListener('scroll', onScroll);
  }, [active]);

  return scrollContentRef;
}

export default useAutoScroll;