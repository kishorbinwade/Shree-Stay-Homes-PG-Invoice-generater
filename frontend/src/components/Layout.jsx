import { useEffect, useState } from 'react';
import { NavLink, Outlet, Link } from 'react-router-dom';
import {
  LayoutDashboard, FilePlus2, History, Users, Settings as SettingsIcon,
  DatabaseBackup, Menu, WifiOff, BedDouble, CalendarPlus, IndianRupee,
  AlarmClock, UtensilsCrossed, Wallet, BarChart3, FileUp,
} from 'lucide-react';
import { useSettings } from '../context/SettingsContext';
import { Sheet, SheetContent, SheetTrigger } from './ui/sheet';
import { Button } from './ui/button';

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, testId: 'nav-dashboard' },
  { to: '/invoices/new', label: 'Create Invoice', icon: FilePlus2, testId: 'nav-create-invoice' },
  { to: '/tenants', label: 'Tenants', icon: Users, testId: 'nav-tenants' },
  { to: '/rooms', label: 'Rooms & Beds', icon: BedDouble, testId: 'nav-rooms' },
  { to: '/billing', label: 'Monthly Billing', icon: CalendarPlus, testId: 'nav-billing' },
  { to: '/history', label: 'Invoices', icon: History, testId: 'nav-history' },
  { to: '/payments', label: 'Payments', icon: IndianRupee, testId: 'nav-payments' },
  { to: '/overdue', label: 'Overdue', icon: AlarmClock, testId: 'nav-overdue' },
  { to: '/food', label: 'Food Orders', icon: UtensilsCrossed, testId: 'nav-food' },
  { to: '/expenses', label: 'Expenses', icon: Wallet, testId: 'nav-expenses' },
  { to: '/reports', label: 'Reports', icon: BarChart3, testId: 'nav-reports' },
  { to: '/import', label: 'Import Google Forms', icon: FileUp, testId: 'nav-import' },
  { to: '/backup', label: 'Backup & Restore', icon: DatabaseBackup, testId: 'nav-backup' },
  { to: '/settings', label: 'Settings', icon: SettingsIcon, testId: 'nav-settings' },
];

function Brand({ settings }) {
  return (
    <Link to="/dashboard" className="flex items-center gap-3 px-5 py-5 border-b border-stone-200" data-testid="brand-home-link">
      {settings.logo ? (
        <img src={settings.logo} alt="PG logo" className="h-10 w-10 rounded-lg object-cover border border-stone-200" />
      ) : (
        <div className="h-10 w-10 rounded-lg bg-terracotta-500 text-white flex items-center justify-center font-heading font-extrabold text-sm">
          SS
        </div>
      )}
      <div className="leading-tight">
        <div className="font-heading font-extrabold text-[13px] tracking-tight text-stone-900">{settings.businessName}</div>
        <div className="text-[11px] text-stone-500">{settings.subtitle}</div>
      </div>
    </Link>
  );
}

function NavItems({ onNavigate }) {
  return (
    <nav className="flex flex-col gap-1 p-3">
      {NAV.map(({ to, label, icon: Icon, testId }) => (
        <NavLink
          key={to}
          to={to}
          onClick={onNavigate}
          data-testid={testId}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-terracotta-500 focus-visible:outline-none ${
              isActive ? 'bg-terracotta-50 text-terracotta-700' : 'text-stone-600 hover:bg-stone-50 hover:text-stone-900'
            }`
          }
        >
          <Icon className="h-4 w-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function OfflineIndicator() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);
  if (online) return null;
  return (
    <div data-testid="offline-indicator" className="fixed bottom-4 left-4 z-50 flex items-center gap-2 rounded-full bg-amber-50 border border-amber-200 px-4 py-2 text-xs font-medium text-amber-800 shadow-sm">
      <WifiOff className="h-3.5 w-3.5" />
      Offline Mode — changes saved locally
    </div>
  );
}

export default function Layout() {
  const { settings, backendDown } = useSettings();
  const [open, setOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#F7F5F2]">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-stone-200 bg-white lg:flex">
        <Brand settings={settings} />
        <NavItems />
        <div className="mt-auto p-4 text-[11px] text-stone-400 border-t border-stone-100">
          Data stays on this device. Backup regularly.
        </div>
      </aside>

      <div className="lg:hidden sticky top-0 z-30 flex items-center gap-2 border-b border-stone-200 bg-white px-3 py-2">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="icon" data-testid="mobile-menu-button" aria-label="Open menu">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-72 p-0 bg-white">
            <Brand settings={settings} />
            <NavItems onNavigate={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
        <div className="font-heading font-extrabold text-sm tracking-tight text-stone-900 truncate">{settings.businessName}</div>
      </div>

      {backendDown && (
        <div data-testid="backend-offline-banner" className="border-b border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700 lg:pl-64">
          Cannot reach the local backend (http://localhost:8001). Start it with ./scripts/run-local.sh — invoices, history and settings need it running.
        </div>
      )}
      <main className="lg:pl-64">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </div>
      </main>
      <OfflineIndicator />
    </div>
  );
}
