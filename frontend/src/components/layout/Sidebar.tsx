import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  CreditCard, 
  AlertTriangle, 
  FileText, 
  Bot, 
  LogOut, 
  ChevronLeft, 
  ChevronRight, 
  Shield, 
  Wifi, 
  WifiOff,
  User as UserIcon,
  Users
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useAlerts } from '../../context/AlertsContext';

export const Sidebar: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout, isAdmin } = useAuth();
  const { pendingCount, isConnected } = useAlerts();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/transactions', label: 'Transactions', icon: CreditCard },
    { 
      to: '/alerts', 
      label: 'Alertes Fraude', 
      icon: AlertTriangle, 
      badge: pendingCount > 0 ? pendingCount : undefined,
      badgeColor: 'bg-amber-500 text-slate-950 font-bold'
    },
    { to: '/reports', label: 'Rapports & Audit', icon: FileText },
    { to: '/agent', label: 'Agent IA (Text-to-SQL)', icon: Bot, highlight: true },
    ...(isAdmin ? [{ to: '/users', label: 'Gestion des Utilisateurs', icon: Users }] : []),
  ];

  return (
    <aside
      className={`h-screen sticky top-0 flex flex-col justify-between border-r border-slate-800/80 bg-slate-950/80 backdrop-blur-xl transition-all duration-300 z-40 ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* En-tête Sidebar */}
      <div>
        <div className="h-16 flex items-center justify-between px-4 border-b border-slate-800/60">
          {!collapsed ? (
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="p-2 rounded-xl bg-blue-600/20 border border-blue-500/30 text-blue-400">
                <Shield className="w-5 h-5" />
              </div>
              <div>
                <h1 className="text-sm font-bold tracking-tight text-white truncate">FRAUD SHIELD</h1>
                <p className="text-[10px] text-slate-400 font-mono">AUTONOMOUS BANK SOC</p>
              </div>
            </div>
          ) : (
            <div className="mx-auto p-2 rounded-xl bg-blue-600/20 text-blue-400">
              <Shield className="w-5 h-5" />
            </div>
          )}

          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800/60 transition"
            title={collapsed ? 'Agrandir' : 'Réduire'}
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="p-3 space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                    isActive
                      ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30 shadow-sm shadow-blue-500/10'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                  } ${collapsed ? 'justify-center' : ''}`
                }
                title={collapsed ? item.label : undefined}
              >
                <Icon className={`w-5 h-5 flex-shrink-0 ${item.highlight ? 'text-indigo-400' : ''}`} />
                {!collapsed && (
                  <span className="flex-1 truncate flex items-center justify-between">
                    {item.label}
                    {item.badge !== undefined && (
                      <span className={`text-[11px] px-1.5 py-0.5 rounded-full ${item.badgeColor}`}>
                        {item.badge}
                      </span>
                    )}
                  </span>
                )}
                {collapsed && item.badge !== undefined && (
                  <span className="absolute top-1 right-1 w-2.5 h-2.5 rounded-full bg-amber-500" />
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Pied de Sidebar : Statut Kafka/WS & Profil Utilisateur */}
      <div className="p-3 border-t border-slate-800/60 space-y-3">
        {/* Statut Temps Réel WebSocket */}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono border ${
            isConnected
              ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40'
              : 'bg-rose-950/40 text-rose-400 border-rose-800/40'
          } ${collapsed ? 'justify-center px-1' : ''}`}
        >
          {isConnected ? (
            <>
              <Wifi className="w-3.5 h-3.5 flex-shrink-0 animate-pulse" />
              {!collapsed && <span>WS KAFKA LIVE</span>}
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5 flex-shrink-0" />
              {!collapsed && <span>WS DÉCONNECTÉ</span>}
            </>
          )}
        </div>

        {/* Profil & Déconnexion */}
        <div className={`flex items-center justify-between gap-2 p-2 rounded-xl bg-slate-900/60 border border-slate-800/50 ${collapsed ? 'flex-col' : ''}`}>
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center text-slate-300 font-semibold text-xs border border-slate-700">
              <UserIcon className="w-4 h-4 text-slate-400" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white truncate">{user?.full_name || user?.username}</p>
                <span className="inline-block text-[10px] text-blue-400 font-mono uppercase bg-blue-950/50 px-1.5 py-0.5 rounded border border-blue-900/40">
                  {isAdmin ? 'ADMIN SOC' : 'ANALYSTE L2'}
                </span>
              </div>
            )}
          </div>

          <button
            onClick={handleLogout}
            className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800/60 rounded-lg transition"
            title="Se déconnecter"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};