import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { SettingsProvider } from "@/context/SettingsContext";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import CreateInvoice from "@/pages/CreateInvoice";
import History from "@/pages/History";
import Tenants from "@/pages/Tenants";
import Settings from "@/pages/Settings";
import Backup from "@/pages/Backup";
import MonthlyBilling from "@/pages/MonthlyBilling";
import Overdue from "@/pages/Overdue";
import FoodOrders from "@/pages/FoodOrders";
import Expenses from "@/pages/Expenses";
import Reports from "@/pages/Reports";
import ImportCSV from "@/pages/ImportCSV";
import RoomsBeds from "@/pages/RoomsBeds";
import Payments from "@/pages/Payments";
import TenantLedger from "@/pages/TenantLedger";
import { Toaster } from "@/components/ui/sonner";

function App() {
  return (
    <SettingsProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/invoices/new" element={<CreateInvoice />} />
            <Route path="/invoices/:id/edit" element={<CreateInvoice />} />
            <Route path="/history" element={<History />} />
            <Route path="/billing" element={<MonthlyBilling />} />
            <Route path="/overdue" element={<Overdue />} />
            <Route path="/food" element={<FoodOrders />} />
            <Route path="/expenses" element={<Expenses />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/import" element={<ImportCSV />} />
            <Route path="/rooms" element={<RoomsBeds />} />
            <Route path="/payments" element={<Payments />} />
            <Route path="/tenants" element={<Tenants />} />
            <Route path="/tenants/:id/ledger" element={<TenantLedger />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/backup" element={<Backup />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors closeButton />
    </SettingsProvider>
  );
}

export default App;
