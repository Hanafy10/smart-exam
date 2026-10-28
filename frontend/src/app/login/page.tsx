'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import {
  ShieldCheck,
  Lock,
  User as UserIcon,
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  Loader2,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { user, loading: authLoading, login } = useAuth();
  const router = useRouter();

  // If already authenticated, redirect based on role
  useEffect(() => {
    if (!authLoading && user) {
      if (user.role === 'admin') {
        router.replace('/admin');
      } else {
        router.replace('/monitoring');
      }
    }
  }, [user, authLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Please enter both username and password.');
      return;
    }

    setError(null);
    setSubmitting(true);

    try {
      const loggedInUser = await login(username.trim(), password);
      if (loggedInUser.role === 'admin') {
        router.push('/admin');
      } else {
        router.push('/monitoring');
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'Authentication failed. Please check your credentials.';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  // If auth is still initializing and user exists, render minimal loader to avoid flash
  if (authLoading && user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
          <p className="text-xs text-slate-400">Verifying active session...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-4 py-12 selection:bg-indigo-500 selection:text-white">
      {/* Background ambient lighting effects */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/2 h-[500px] w-[600px] -translate-x-1/2 rounded-full bg-indigo-600/15 blur-[120px]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-40 right-1/4 h-[400px] w-[500px] rounded-full bg-blue-600/10 blur-[100px]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-1/3 left-1/4 h-[300px] w-[300px] rounded-full bg-cyan-600/10 blur-[90px]"
      />

      {/* Login Card */}
      <div className="relative z-10 w-full max-w-md">
        {/* Glow border wrapper */}
        <div className="rounded-3xl border border-slate-800/80 bg-slate-900/80 p-8 shadow-2xl backdrop-blur-2xl sm:p-10 transition-all duration-300 hover:border-slate-700/80">
          
          {/* Header & Logo */}
          <div className="flex flex-col items-center text-center">
            <div className="relative mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo-600/30 via-indigo-500/20 to-cyan-500/10 p-0.5 shadow-xl ring-1 ring-indigo-500/40">
              <div className="flex h-full w-full items-center justify-center rounded-[14px] bg-slate-900/90 text-indigo-400">
                <ShieldCheck className="h-9 w-9 transition-transform duration-300 hover:scale-105" />
              </div>
              <div className="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 border border-emerald-400/40 text-emerald-400">
                <Sparkles className="h-2.5 w-2.5" />
              </div>
            </div>

            <div className="inline-flex items-center gap-1.5 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-[11px] font-medium text-indigo-300 mb-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Academic Proctoring Platform
            </div>

            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Smart Exam Proctor
            </h1>
            <p className="mt-1 text-xs text-slate-400 max-w-xs">
              AI-assisted in-person exam supervision and integrity platform
            </p>
          </div>

          {/* Error Message Box */}
          {error && (
            <div
              role="alert"
              className="mt-6 flex items-start gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-200 transition-all animate-in fade-in slide-in-from-top-1"
            >
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
              <div className="flex-1">
                <span className="font-semibold text-rose-300">Sign-in error:</span>{' '}
                <span>{error}</span>
              </div>
              <button
                type="button"
                onClick={() => setError(null)}
                className="text-rose-400/80 hover:text-rose-200 text-xs font-medium cursor-pointer"
                aria-label="Dismiss alert"
              >
                ✕
              </button>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label
                htmlFor="username"
                className="block text-xs font-medium text-slate-300 mb-1.5"
              >
                Username <span className="text-slate-500">/ اسم المستخدم</span>
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
                  <UserIcon className="h-4 w-4" />
                </div>
                <input
                  id="username"
                  name="username"
                  type="text"
                  required
                  autoComplete="username"
                  autoFocus
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    if (error) setError(null);
                  }}
                  className="w-full rounded-xl border border-slate-700/80 bg-slate-950/60 pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 transition-all focus:border-indigo-500 focus:bg-slate-900/90 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 disabled:opacity-50"
                  placeholder="Enter your username or email"
                  disabled={submitting}
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="password"
                  className="block text-xs font-medium text-slate-300"
                >
                  Password <span className="text-slate-500">/ كلمة المرور</span>
                </label>
              </div>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (error) setError(null);
                  }}
                  className="w-full rounded-xl border border-slate-700/80 bg-slate-950/60 pl-10 pr-10 py-2.5 text-sm text-white placeholder-slate-500 transition-all focus:border-indigo-500 focus:bg-slate-900/90 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 disabled:opacity-50"
                  placeholder="Enter your password"
                  disabled={submitting}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-slate-400 hover:text-slate-200 focus:outline-none transition-colors cursor-pointer"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={submitting || !username.trim() || !password}
                className="group relative flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/30 transition-all duration-200 hover:from-indigo-500 hover:to-indigo-400 hover:shadow-indigo-500/40 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:pointer-events-none disabled:opacity-50 cursor-pointer"
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Authenticating...</span>
                  </>
                ) : (
                  <>
                    <span>Sign In / تسجيل الدخول</span>
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Secure indicator footer */}
          <div className="mt-8 border-t border-slate-800/80 pt-4">
            <div className="flex items-center justify-center gap-2 text-[11px] text-slate-500">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500/80" />
              <span>Role-Based Access Control • Secured with JWT &amp; Argon2</span>
            </div>
            <p className="mt-1 text-center text-[10px] text-slate-600">
              Authorized access only for Exam Administrators and Invigilators
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
