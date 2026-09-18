import { useCallback, useEffect, useState } from 'react';
import { fetchInvoices, fetchDashboardStats } from '../lib/api';

export function useDashboardData() {
  const [data, setData] = useState({ invoices: [], stats: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    let timer;
    let inFlight = false;
    let failed = false;
    const load = async () => {
      if (cancelled || inFlight) return;
      inFlight = true;
      clearTimeout(timer);
      setLoading(true);
      try {
        const [invoices, stats] = await Promise.all([fetchInvoices(), fetchDashboardStats()]);
        if (cancelled) return;
        setData({ invoices, stats });
        setError('');
        failed = false;
      } catch (e) {
        if (cancelled) return;
        failed = true;
        setError(e.message);
        timer = setTimeout(load, 5000);
      } finally {
        inFlight = false;
        if (!cancelled) setLoading(false);
      }
    };
    const resume = () => { if (failed) load(); };
    window.addEventListener('online', resume);
    window.addEventListener('focus', resume);
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      window.removeEventListener('online', resume);
      window.removeEventListener('focus', resume);
    };
  }, [attempt]);

  return { ...data, loading, error, retry };
}