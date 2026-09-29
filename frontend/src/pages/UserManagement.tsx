import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { User, CreatedUserResponse } from '../types';
import {
  UserPlus,
  Users,
  Copy,
  CheckCircle2,
  X,
  Shield,
  AlertCircle,
  Loader2,
} from 'lucide-react';

export const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [createdCreds, setCreatedCreds] = useState<CreatedUserResponse | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.auth.listUsers();
      setUsers(data);
    } catch (err: any) {
      setError(err.message || 'Impossible de charger les utilisateurs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !email.trim()) {
      setFormError('Veuillez renseigner le nom complet et l\'email.');
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      const result = await api.auth.createAnalyst(fullName.trim(), email.trim());
      setCreatedCreds(result);
      setShowForm(false);
      setFullName('');
      setEmail('');
      await loadUsers();
    } catch (err: any) {
      setFormError(err.message || 'Erreur lors de la création du compte.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopy = (value: string, label: string) => {
    navigator.clipboard.writeText(value);
    setCopied(label);
    setTimeout(() => setCopied(null), 1500);
  };

  return (
    <div className="p-6 space-y-6">
      {/* En-tête */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2.5">
            <Users className="w-5 h-5 text-blue-400" />
            Gestion des Utilisateurs
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Créez et gérez les comptes Data Analystes du SOC Fraude.
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-sm font-semibold shadow-lg shadow-blue-600/20 transition"
        >
          <UserPlus className="w-4 h-4" />
          Ajouter un Data Analyste
        </button>
      </div>

      {/* Liste des utilisateurs */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden">
        {loading ? (
          <div className="p-10 flex items-center justify-center text-slate-400 gap-2">
            <Loader2 className="w-5 h-5 animate-spin" />
            Chargement...
          </div>
        ) : error ? (
          <div className="p-6 flex items-center gap-2.5 text-rose-300 text-sm">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider">
                <th className="text-left px-5 py-3 font-semibold">Nom complet</th>
                <th className="text-left px-5 py-3 font-semibold">Identifiant</th>
                <th className="text-left px-5 py-3 font-semibold">Email</th>
                <th className="text-left px-5 py-3 font-semibold">Rôle</th>
                <th className="text-left px-5 py-3 font-semibold">Créé le</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-slate-800/60 hover:bg-slate-800/30 transition">
                  <td className="px-5 py-3 text-white font-medium">{u.full_name}</td>
                  <td className="px-5 py-3 text-slate-300 font-mono">{u.username}</td>
                  <td className="px-5 py-3 text-slate-400">{u.email}</td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-mono uppercase ${
                        u.role === 'admin'
                          ? 'bg-indigo-950/50 text-indigo-400 border border-indigo-900/40'
                          : 'bg-blue-950/50 text-blue-400 border border-blue-900/40'
                      }`}
                    >
                      {u.role === 'admin' && <Shield className="w-3 h-3" />}
                      {u.role}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-slate-500 text-xs">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString('fr-FR') : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal : formulaire de création */}
      {showForm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl">
            <div className="flex items-center justify-between p-5 border-b border-slate-800">
              <h2 className="text-sm font-bold text-white">Nouveau Data Analyste</h2>
              <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="p-5 space-y-4">
              {formError && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-red-950/60 border border-red-800/60 text-red-300 text-xs">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {formError}
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Nom complet
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Ex: Fatima Zahra Salahmi"
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-700 bg-slate-950/60 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                  disabled={submitting}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Email professionnel
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="fatima.zahra@bank-security.com"
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-700 bg-slate-950/60 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                  disabled={submitting}
                />
              </div>
              <p className="text-xs text-slate-500">
                L'identifiant et le mot de passe seront générés automatiquement et affichés une seule fois après création.
              </p>
              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-sm font-semibold transition disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
                Créer le compte
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Modal : identifiants générés (affichés une seule fois) */}
      {createdCreds && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-md rounded-2xl border border-emerald-800/60 bg-slate-900 shadow-2xl">
            <div className="p-5 border-b border-slate-800 flex items-center gap-2.5">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <h2 className="text-sm font-bold text-white">Compte créé avec succès</h2>
            </div>
            <div className="p-5 space-y-4">
              <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-800/50 text-amber-300 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>
                  Ce mot de passe ne sera plus jamais affiché. Copiez-le et transmettez-le
                  à {createdCreds.user.full_name} via un canal sécurisé.
                </span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                  Identifiant
                </label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sm text-white font-mono">
                    {createdCreds.generated_username}
                  </code>
                  <button
                    onClick={() => handleCopy(createdCreds.generated_username, 'username')}
                    className="p-2 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-300 transition"
                  >
                    {copied === 'username' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                  Mot de passe
                </label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sm text-white font-mono">
                    {createdCreds.generated_password}
                  </code>
                  <button
                    onClick={() => handleCopy(createdCreds.generated_password, 'password')}
                    className="p-2 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-300 transition"
                  >
                    {copied === 'password' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              <button
                onClick={() => setCreatedCreds(null)}
                className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-sm font-semibold transition"
              >
                J'ai bien noté ces identifiants
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};