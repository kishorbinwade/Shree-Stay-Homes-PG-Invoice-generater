import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getSettings, saveSettings, DEFAULT_SETTINGS } from '../lib/db';

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getSettings()
      .then((s) => setSettings(s))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const updateSettings = useCallback(async (next) => {
    await saveSettings(next);
    setSettings(next);
  }, []);

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, loaded }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  return useContext(SettingsContext);
}
