import { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { fetchSettings, saveSettings as apiSaveSettings, DEFAULT_SETTINGS } from '../lib/api';

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);
  const [backendDown, setBackendDown] = useState(false);
  const [checkingBackend, setCheckingBackend] = useState(false);
  const retryRef = useRef(() => {});
  const retryBackend = useCallback(() => retryRef.current(), []);

  useEffect(() => {
    let cancelled = false;
    let timer;
    let inFlight = false;
    let failures = 0;
    const load = async () => {
      if (cancelled || inFlight) return;
      clearTimeout(timer);
      inFlight = true;
      setCheckingBackend(true);
      try {
        const s = await fetchSettings();
        if (cancelled) return;
        failures = 0;
        setSettings(s);
        setBackendDown(false);
        setLoaded(true);
      } catch (e) {
        if (cancelled) return;
        failures += 1;
        if (failures >= 3) setBackendDown(true);
        // Keep retrying after the initial grace period, including in an open preview tab.
        timer = setTimeout(load, failures < 3 ? 1500 : 5000);
      } finally {
        inFlight = false;
        if (!cancelled) setCheckingBackend(false);
      }
    };
    const resume = () => { if (failures > 0) load(); };
    const onVisible = () => { if (document.visibilityState === 'visible') resume(); };
    retryRef.current = load;
    window.addEventListener('online', resume);
    window.addEventListener('focus', resume);
    document.addEventListener('visibilitychange', onVisible);
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      retryRef.current = () => {};
      window.removeEventListener('online', resume);
      window.removeEventListener('focus', resume);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []);

  const updateSettings = useCallback(async (next) => {
    await apiSaveSettings(next);
    setSettings(next);
  }, []);

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, loaded, backendDown, checkingBackend, retryBackend }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  return useContext(SettingsContext);
}
