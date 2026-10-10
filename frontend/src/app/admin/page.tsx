'use client';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import {
  getAdminRooms,
  createAdminRoom,
  getAdminInvigilators,
  createAdminInvigilator,
  updateAdminInvigilator,
  deleteAdminInvigilator,
} from '@/lib/api';
import { ExamRoom, Invigilator } from '@/lib/types';
import {
  ShieldAlert,
  Users,
  Building,
  Plus,
  RefreshCw,
  LogOut,
  CheckCircle2,
  XCircle,
  KeyRound,
  Trash2,
  AlertTriangle,
  DoorOpen,
  Camera,
  Search,
} from 'lucide-react';

export default function AdminPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<'invigilators' | 'rooms'>('invigilators');
  const [rooms, setRooms] = useState<ExamRoom[]>([]);
  const [invigilators, setInvigilators] = useState<Invigilator[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Modals state
  const [showAddInvModal, setShowAddInvModal] = useState(false);
  const [showAddRoomModal, setShowAddRoomModal] = useState(false);
  const [showResetPasswordModal, setShowResetPasswordModal] = useState<Invigilator | null>(null);

  // Form states
  const [newInvUsername, setNewInvUsername] = useState('');
  const [newInvPassword, setNewInvPassword] = useState('');
  const [newInvEmail, setNewInvEmail] = useState('');
  const [newInvRoomId, setNewInvRoomId] = useState<number | ''>('');

  const [newRoomName, setNewRoomName] = useState('');
  const [newRoomBuilding, setNewRoomBuilding] = useState('');
  const [newRoomCapacity, setNewRoomCapacity] = useState(30);

  const [resetPasswordVal, setResetPasswordVal] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // RBAC Guard: Admin Only
  useEffect(() => {
    if (!authLoading) {
      if (!user) {
        router.push('/login');
      } else if (user.role !== 'admin') {
        router.push('/monitoring');
      }
    }
  }, [user, authLoading, router]);

  const loadData = useCallback(async () => {
    try {
      setLoadingData(true);
      setError(null);
      const [fetchedRooms, fetchedInvs] = await Promise.all([
        getAdminRooms(),
        getAdminInvigilators(),
      ]);
      setRooms(fetchedRooms);
      setInvigilators(fetchedInvs);
      if (fetchedRooms.length > 0 && newInvRoomId === '') {
        setNewInvRoomId(fetchedRooms[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch admin data');
    } finally {
      setLoadingData(false);
    }
  }, [newInvRoomId]);

  useEffect(() => {
    if (user && user.role === 'admin') {
      loadData();
    }
  }, [user, loadData]);

  // Handle Add Invigilator
  const handleAddInvigilator = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newInvRoomId) {
      setError('Please select an exam room');
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await createAdminInvigilator({
        username: newInvUsername.trim(),
        password: newInvPassword,
        email: newInvEmail.trim() || undefined,
        assigned_room_id: Number(newInvRoomId),
      });
      setShowAddInvModal(false);
      setNewInvUsername('');
      setNewInvPassword('');
      setNewInvEmail('');
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to create invigilator');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Add Room
  const handleAddRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    setError(null);
    try {
      await createAdminRoom({
        name: newRoomName.trim(),
        building: newRoomBuilding.trim() || undefined,
        capacity: Number(newRoomCapacity),
      });
      setShowAddRoomModal(false);
      setNewRoomName('');
      setNewRoomBuilding('');
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to create room');
    } finally {
      setActionLoading(false);
    }
  };

  // Toggle Invigilator Active/Inactive
  const handleToggleActive = async (inv: Invigilator) => {
    try {
      await updateAdminInvigilator(inv.id, { is_active: !inv.is_active });
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to update invigilator status');
    }
  };

  // Change Invigilator Room Assignment
  const handleReassignRoom = async (invId: number, targetRoomId: number) => {
    try {
      await updateAdminInvigilator(invId, { assigned_room_id: targetRoomId });
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to reassign room');
    }
  };

  // Reset Password
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showResetPasswordModal || !resetPasswordVal) return;
    setActionLoading(true);
    try {
      await updateAdminInvigilator(showResetPasswordModal.id, { password: resetPasswordVal });
      setShowResetPasswordModal(null);
      setResetPasswordVal('');
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to reset password');
    } finally {
      setActionLoading(false);
    }
  };

  // Delete Invigilator
  const handleDeleteInvigilator = async (id: number, username: string) => {
    if (!confirm(`Are you sure you want to permanently delete invigilator "${username}"?`)) return;
    try {
      await deleteAdminInvigilator(id);
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to delete invigilator');
    }
  };

  if (authLoading || (user && user.role !== 'admin')) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <RefreshCw className="h-6 w-6 animate-spin text-indigo-400 mr-2" />
        <span>Authenticating Admin Session...</span>
      </div>
    );
  }

  const filteredInvigilators = invigilators.filter((inv) =>
    inv.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (inv.email && inv.email.toLowerCase().includes(searchQuery.toLowerCase())) ||
    (inv.assigned_room_name && inv.assigned_room_name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navigation */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md px-6 py-4 flex items-center justify-between sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white flex items-center gap-2">
              <span>Admin Dashboard</span>
              <span className="text-slate-400 text-sm font-normal">|</span>
              <span className="text-indigo-400 font-semibold font-arabic text-sm">لوحة المسؤول</span>
            </h1>
            <p className="text-xs text-slate-400">
              Exam Room Assignments &amp; Invigilator Access Control (REST Management)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <span className="block text-xs font-semibold text-slate-200">{user?.username}</span>
            <span className="inline-block text-[10px] text-emerald-400 font-medium bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
              System Administrator
            </span>
          </div>

          <button
            onClick={logout}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/30 transition-all cursor-pointer"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
        {/* Error Alert */}
        {error && (
          <div className="mb-6 flex items-center justify-between rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-xs text-red-300">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-400" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-slate-400 hover:text-white">
              ✕
            </button>
          </div>
        )}

        {/* Stats Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-medium">Total Exam Rooms</span>
              <Building className="h-4 w-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold text-white">{rooms.length}</div>
            <div className="text-[11px] text-slate-500 mt-1">Active halls available for exams</div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-medium">Invigilators Registered</span>
              <Users className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-white">{invigilators.length}</div>
            <div className="text-[11px] text-slate-500 mt-1">
              {invigilators.filter((i) => i.is_active).length} active / {invigilators.filter((i) => !i.is_active).length} deactivated
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-medium">Assigned Rooms</span>
              <DoorOpen className="h-4 w-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-white">
              {invigilators.filter((i) => i.assigned_room_id !== null).length}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">Monitored rooms with proctors</div>
          </div>
        </div>

        {/* Tab Controls & Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4 mb-6">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('invigilators')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'invigilators'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              <Users className="h-3.5 w-3.5" />
              <span>المراقبون / Invigilators ({invigilators.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('rooms')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'rooms'
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              <Building className="h-3.5 w-3.5" />
              <span>قاعات الامتحانات / Exam Rooms ({rooms.length})</span>
            </button>
          </div>

          <div className="flex items-center gap-3">
            {activeTab === 'invigilators' && (
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
                <input
                  type="text"
                  placeholder="Filter invigilators..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="rounded-xl border border-slate-800 bg-slate-900 px-8 py-1.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>
            )}

            <button
              onClick={loadData}
              disabled={loadingData}
              className="flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-400 hover:text-white hover:border-slate-700 transition-all cursor-pointer"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loadingData ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>

            {activeTab === 'invigilators' ? (
              <button
                onClick={() => setShowAddInvModal(true)}
                className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 hover:bg-indigo-500 transition-all cursor-pointer"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>إضافة مراقب / Add Invigilator</span>
              </button>
            ) : (
              <button
                onClick={() => setShowAddRoomModal(true)}
                className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 hover:bg-indigo-500 transition-all cursor-pointer"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>إضافة قاعة / Add Room</span>
              </button>
            )}
          </div>
        </div>

        {/* Tab 1: Invigilators Table */}
        {activeTab === 'invigilators' && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="px-5 py-3">Invigilator</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Assigned Exam Room</th>
                    <th className="px-5 py-3">Created</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredInvigilators.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-8 text-center text-slate-500">
                        {loadingData ? 'Loading invigilators...' : 'No invigilator accounts found. Click "Add Invigilator" to create one.'}
                      </td>
                    </tr>
                  ) : (
                    filteredInvigilators.map((inv) => (
                      <tr key={inv.id} className="hover:bg-slate-800/40 transition-colors">
                        <td className="px-5 py-3.5">
                          <div className="font-semibold text-white">{inv.username}</div>
                          {inv.email && <div className="text-[11px] text-slate-400">{inv.email}</div>}
                        </td>

                        <td className="px-5 py-3.5">
                          {inv.is_active ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                              <CheckCircle2 className="h-3 w-3" />
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-red-400 bg-red-500/10 px-2.5 py-0.5 rounded-full border border-red-500/20">
                              <XCircle className="h-3 w-3" />
                              Deactivated
                            </span>
                          )}
                        </td>

                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-2">
                            <select
                              value={inv.assigned_room_id || ''}
                              onChange={(e) => handleReassignRoom(inv.id, Number(e.target.value))}
                              className="rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs text-white focus:border-indigo-500 focus:outline-none"
                            >
                              {rooms.map((r) => (
                                <option key={r.id} value={r.id}>
                                  {r.name} {r.building ? `(${r.building})` : ''}
                                </option>
                              ))}
                            </select>
                          </div>
                        </td>

                        <td className="px-5 py-3.5 text-slate-400">
                          {new Date(inv.created_at).toLocaleDateString()}
                        </td>

                        <td className="px-5 py-3.5 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleToggleActive(inv)}
                              title={inv.is_active ? 'Deactivate Account' : 'Activate Account'}
                              className={`rounded-lg px-2.5 py-1 font-medium transition-all cursor-pointer ${
                                inv.is_active
                                  ? 'bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 border border-amber-500/30'
                                  : 'bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 border border-emerald-500/30'
                              }`}
                            >
                              {inv.is_active ? 'Deactivate' : 'Activate'}
                            </button>

                            <button
                              onClick={() => setShowResetPasswordModal(inv)}
                              title="Reset Password"
                              className="rounded-lg border border-slate-700 bg-slate-800 p-1.5 text-slate-300 hover:text-white hover:bg-slate-700 transition-all cursor-pointer"
                            >
                              <KeyRound className="h-3.5 w-3.5" />
                            </button>

                            <button
                              onClick={() => handleDeleteInvigilator(inv.id, inv.username)}
                              title="Delete Account"
                              className="rounded-lg border border-red-500/20 bg-red-500/10 p-1.5 text-red-400 hover:bg-red-500/20 transition-all cursor-pointer"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 2: Exam Rooms Table */}
        {activeTab === 'rooms' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {rooms.length === 0 ? (
              <div className="col-span-full rounded-2xl border border-slate-800 bg-slate-900/60 p-8 text-center text-slate-500">
                No exam rooms configured. Click "Add Room" to create one.
              </div>
            ) : (
              rooms.map((room) => (
                <div
                  key={room.id}
                  className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-lg flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-indigo-400 bg-indigo-600/10 px-2 py-0.5 rounded-md border border-indigo-500/20">
                        Room #{room.id}
                      </span>
                      <span className="text-xs text-slate-400 flex items-center gap-1">
                        <Camera className="h-3.5 w-3.5 text-emerald-400" />
                        {room.cameras.length} camera(s)
                      </span>
                    </div>

                    <h3 className="text-lg font-bold text-white mb-1">{room.name}</h3>
                    <p className="text-xs text-slate-400 mb-4">
                      {room.building || 'Main Campus Building'} • Capacity: {room.capacity} students
                    </p>
                  </div>

                  <div className="border-t border-slate-800/80 pt-3 flex items-center justify-between text-xs text-slate-400">
                    <span className="flex items-center gap-1">
                      <Users className="h-3.5 w-3.5 text-slate-500" />
                      {room.invigilator_count} Invigilator(s) assigned
                    </span>
                    <span className="text-emerald-400 font-medium">Ready for Exam</span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </main>

      {/* Modal: Add Invigilator */}
      {showAddInvModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-white mb-1">Add New Invigilator / إضافة مراقب</h2>
            <p className="text-xs text-slate-400 mb-4">
              Create an invigilator account with strict assignment to an exam room.
            </p>

            <form onSubmit={handleAddInvigilator} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Username / اسم المستخدم</label>
                <input
                  type="text"
                  required
                  value={newInvUsername}
                  onChange={(e) => setNewInvUsername(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                  placeholder="e.g. invigilator_hall1"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Email / البريد الإلكتروني (Optional)</label>
                <input
                  type="email"
                  value={newInvEmail}
                  onChange={(e) => setNewInvEmail(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                  placeholder="invigilator@smartexam.edu"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Password / كلمة المرور (Min 6 chars)</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={newInvPassword}
                  onChange={(e) => setNewInvPassword(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                  placeholder="••••••••••••"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Assigned Exam Room / تعيين القاعة</label>
                <select
                  required
                  value={newInvRoomId}
                  onChange={(e) => setNewInvRoomId(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="" disabled>Select exam room</option>
                  {rooms.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} {r.building ? `(${r.building})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddInvModal(false)}
                  className="rounded-xl border border-slate-700 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 hover:bg-indigo-500 disabled:opacity-50"
                >
                  {actionLoading ? 'Creating...' : 'Create Invigilator'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Add Room */}
      {showAddRoomModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-white mb-1">Add Exam Room / إضافة قاعة امتحان</h2>
            <p className="text-xs text-slate-400 mb-4">
              Register a new physical exam room in the system.
            </p>

            <form onSubmit={handleAddRoom} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Room Name / اسم القاعة</label>
                <input
                  type="text"
                  required
                  value={newRoomName}
                  onChange={(e) => setNewRoomName(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                  placeholder="e.g. Hall 304"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Building / المبنى</label>
                <input
                  type="text"
                  value={newRoomBuilding}
                  onChange={(e) => setNewRoomBuilding(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                  placeholder="e.g. Science Building B"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Capacity / سعة الطلاب</label>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={newRoomCapacity}
                  onChange={(e) => setNewRoomCapacity(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddRoomModal(false)}
                  className="rounded-xl border border-slate-700 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 hover:bg-indigo-500 disabled:opacity-50"
                >
                  {actionLoading ? 'Creating...' : 'Create Room'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Reset Password */}
      {showResetPasswordModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <h2 className="text-base font-bold text-white mb-1">
              Reset Password for {showResetPasswordModal.username}
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              Enter a new secure password (minimum 6 characters).
            </p>

            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">New Password</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={resetPasswordVal}
                  onChange={(e) => setResetPasswordVal(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                  placeholder="••••••••••••"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowResetPasswordModal(null)}
                  className="rounded-xl border border-slate-700 px-3.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="rounded-xl bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 hover:bg-indigo-500 disabled:opacity-50"
                >
                  {actionLoading ? 'Updating...' : 'Save New Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
