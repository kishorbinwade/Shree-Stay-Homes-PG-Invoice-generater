import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { fetchSettings, saveSettings as apiSaveSettings, DEFAULT_SETTINGS } from '../lib/api';

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);
  const [backendDown, setBackendDown] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async (attempt = 1) => {
      try {
        const s = await fetchSettings();
        if (cancelled) return;
        setSettings(s);
        setBackendDown(false);
        setLoaded(true);
      } catch (e) {
        if (cancelled) return;
        if (attempt < 3) {
          setTimeout(() => load(attempt + 1), 1500);
        } else {
          setBackendDown(true);
          setLoaded(true);
        }
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const updateSettings = useCallback(async (next) => {
    await apiSaveSettings(next);
    setSettings(next);
  }, []);

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, loaded, backendDown }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  return useContext(SettingsContext);
}
