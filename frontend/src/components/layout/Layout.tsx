import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { ToastContainer } from '../ui/ToastContainer';
import { Menu, X, Bell } from 'lucide-react';
import { useAlerts } from '../../context/AlertsContext';
import { useNavigate } from 'react-router-dom';

export const Layout: React.FC = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { pendingCount } = useAlerts();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Sidebar Desktop */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Sidebar Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <div className="relative z-10 w-64 bg-slate-950 shadow-2xl">
            <Sidebar />
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute top-4 right-4 text-slate-400 p-1 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto max-h-screen">
        {/* Mobile Header */}
        <header className="md:hidden flex items-center justify-between px-4 h-14 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-30">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-2">
            <img src="/assets/logo.png" alt="Logo" className="w-5 h-5 object-contain" />
            <span className="font-bold text-sm tracking-tight text-white">Fraud Guard</span>
          </div>

          <button
            onClick={() => navigate('/alerts')}
            className="relative p-1.5 text-slate-400 hover:text-white"
          >
            <Bell className="w-5 h-5" />
            {pendingCount > 0 && (
              <span className="absolute top-1 right-1 w-2.5 h-2.5 rounded-full bg-amber-500 animate-ping" />
            )}
          </button>
        </header>

        {/* Content Outlet */}
        <main className="flex-1 p-4 md:p-8 max-w-7xl mx-auto w-full">
          <Outlet />
        </main>
      </div>

      {/* Toast notifications pour les alertes Kafka temps réel */}
      <ToastContainer />
    </div>
  );
};
