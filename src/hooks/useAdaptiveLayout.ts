import { useState, useEffect } from 'react';
import type { LayoutTier } from '../types/library';

export function useAdaptiveLayout() {
  const [layoutTier, setLayoutTier] = useState<LayoutTier>('TIER_1_DESKTOP');
  const [splitRightTab, setSplitRightTab] = useState<'02' | '03'>('02');
  const [mobileTab, setMobileTab] = useState<'01' | '02' | '03'>('01');
  const [windowDimensions, setWindowDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    function handleResize() {
      const w = window.innerWidth;
      const h = window.innerHeight;
      setWindowDimensions({ width: w, height: h });

      if (w >= 1180) {
        setLayoutTier('TIER_1_DESKTOP');
      } else if (w >= 768) {
        setLayoutTier('TIER_2_SPLIT');
      } else {
        setLayoutTier('TIER_3_MOBILE');
      }
    }

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return {
    layoutTier,
    splitRightTab,
    setSplitRightTab,
    mobileTab,
    setMobileTab,
    windowDimensions,
  };
}
