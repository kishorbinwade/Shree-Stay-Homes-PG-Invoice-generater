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
            <Route path="/tenants" element={<Tenants />} />
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
