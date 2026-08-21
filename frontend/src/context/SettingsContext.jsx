import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { fetchSettings, saveSettings as apiSaveSettings, DEFAULT_SETTINGS } from '../lib/api';

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);
  const [backendDown, setBackendDown] = useState(false);

  useEffect(() => {
    fetchSettings()
      .then((s) => { setSettings(s); setBackendDown(false); })
      .catch(() => setBackendDown(true))
      .finally(() => setLoaded(true));
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
