'use client';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import {
  getMyRoom,
  getMyRoomSummary,
  getMyRoomEvents,
  getVideoFeedUrl,
  getMonitoringWsUrl,
  pauseExam,
  resumeExam,
} from '@/lib/api';
import { ExamRoom, RoomMonitoringSummary, ViolationEvent, StudentTrack } from '@/lib/types';
import { useWebSocket } from '@/hooks/useWebSocket';
import {
  Eye,
  Camera,
  AlertTriangle,
  Users,
  ShieldAlert,
  Play,
  Pause,
  LogOut,
  RefreshCw,
  Building,
  CheckCircle2,
  XCircle,
  Clock,
  Compass,
  FileText,
  AlertCircle,
  ImageIcon,
} from 'lucide-react';

export default function MonitoringPage() {
  const { user, token, loading: authLoading, logout } = useAuth();
  const router = useRouter();

  const [room, setRoom] = useState<ExamRoom | null>(null);
  const [summary, setSummary] = useState<RoomMonitoringSummary | null>(null);
  const [events, setEvents] = useState<ViolationEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null);

  // Authenticated WebSocket URL strictly for assigned room
  const wsUrl = getMonitoringWsUrl(token);

  const {
    isConnected: wsConnected,
    liveCount,
    fps,
    tracks,
    recentEvents: wsEvents,
    examStatus,
    pauseReason,
  } = useWebSocket(token && user?.assigned_room_id ? wsUrl : '');

  // Guard: Invigilator Only
  useEffect(() => {
    if (!authLoading) {
      if (!user) {
        router.push('/login');
      } else if (user.role === 'admin') {
        router.push('/admin');
      }
    }
  }, [user, authLoading, router]);

  const loadRoomData = useCallback(async () => {
    if (!user?.assigned_room_id) return;
    try {
      setLoading(true);
      setError(null);
      const [roomData, summaryData, eventsData] = await Promise.all([
        getMyRoom(),
        getMyRoomSummary(),
        getMyRoomEvents(30),
      ]);
      setRoom(roomData);
      setSummary(summaryData);
      setEvents(eventsData);
    } catch (err: any) {
      setError(err.message || 'Failed to load room monitoring data');
    } finally {
      setLoading(false);
    }
  }, [user?.assigned_room_id]);

  useEffect(() => {
    if (user && user.role === 'invigilator' && user.assigned_room_id) {
      loadRoomData();
    }
  }, [user, loadRoomData]);

  // Combine REST initial events with live WebSocket events without duplicates
  const allEvents = [...wsEvents, ...events].filter(
    (event, index, self) => index === self.findIndex((e) => e.id === event.id)
  );

  const handlePause = async () => {
    try {
      await pauseExam('Invigilator manual pause');
      await loadRoomData();
    } catch (err: any) {
      setError(err.message || 'Failed to pause exam');
    }
  };

  const handleResume = async () => {
    try {
      await resumeExam();
      await loadRoomData();
    } catch (err: any) {
      setError(err.message || 'Failed to resume exam');
    }
  };

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <RefreshCw className="h-6 w-6 animate-spin text-indigo-400 mr-2" />
        <span>Loading invigilator station...</span>
      </div>
    );
  }

  // Handle Unassigned Invigilator State (Mandatory User Requirement)
  if (user && !user.assigned_room_id) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-950 px-4 text-center">
        <div className="w-full max-w-lg rounded-2xl border border-amber-500/30 bg-slate-900/90 p-8 shadow-2xl backdrop-blur-md">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 mb-4">
            <AlertCircle className="h-8 w-8" />
          </div>
          <h2 className="text-xl font-bold text-white mb-2">No Exam Room Assigned</h2>
          <p className="text-amber-300 font-arabic text-sm mb-3">لا توجد قاعة معينة لك حالياً</p>
          <p className="text-xs text-slate-400 mb-6 leading-relaxed">
            Your account ({user.username}) is active, but you have not yet been assigned to a specific exam room. Please contact your system administrator to assign an exam room.
          </p>
          <button
            onClick={logout}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800 px-5 py-2.5 text-xs font-semibold text-white hover:bg-slate-700 transition-all cursor-pointer"
          >
            <LogOut className="h-4 w-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md px-6 py-3.5 flex flex-wrap items-center justify-between gap-4 sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
            <Eye className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-white">Invigilator Dashboard</h1>
              <span className="text-slate-500 text-xs">|</span>
              <span className="text-indigo-400 font-semibold font-arabic text-xs">لوحة مراقب اللجنة</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
              <Building className="h-3.5 w-3.5 text-slate-500" />
              <span className="text-white font-medium">{room?.name || 'Assigned Room'}</span>
              <span>•</span>
              <span>{room?.building || 'Main Campus'}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Honest Violence Detection Status Badge */}
          <div className="hidden md:flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1 text-[11px] text-slate-400">
            <span className="h-2 w-2 rounded-full bg-slate-500"></span>
            <span>كشف العنف غير متاح / Violence detection unavailable</span>
          </div>

          {/* WebSocket Status */}
          <div className="flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900 px-2.5 py-1 text-[11px]">
            <span className={`h-2 w-2 rounded-full ${wsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`}></span>
            <span className="text-slate-300">{wsConnected ? 'Live WS' : 'Connecting'}</span>
          </div>

          <button
            onClick={logout}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/30 transition-all cursor-pointer"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Sign Out</span>
          </button>
        </div>
      </header>

      {/* Main Monitoring Workspace */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-6">
        {error && (
          <div className="flex items-center justify-between rounded-xl border border-red-500/30 bg-red-500/10 p-3.5 text-xs text-red-300">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-400" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-slate-400 hover:text-white">✕</button>
          </div>
        )}

        {/* Real Metrics Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="text-[11px] font-medium text-slate-400 mb-1 flex items-center justify-between">
              <span>Total Students</span>
              <Users className="h-3.5 w-3.5 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold text-white">
              {liveCount > 0 ? liveCount : (summary?.total_students || 0)}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Live student count</div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="text-[11px] font-medium text-slate-400 mb-1 flex items-center justify-between">
              <span>Suspicious Students</span>
              <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-amber-400">
              {summary?.suspicious_students || 0}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Violations recorded</div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="text-[11px] font-medium text-slate-400 mb-1 flex items-center justify-between">
              <span>Total Violations</span>
              <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
            </div>
            <div className="text-2xl font-bold text-red-400">
              {summary?.total_violations || allEvents.length}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Assigned hall events</div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="text-[11px] font-medium text-slate-400 mb-1 flex items-center justify-between">
              <span>Camera Stream</span>
              <Camera className="h-3.5 w-3.5 text-emerald-400" />
            </div>
            <div className="text-base font-bold text-emerald-400 flex items-center gap-1.5 mt-1">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>Online ({fps > 0 ? `${fps} FPS` : 'Ready'})</span>
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              Room #{user?.assigned_room_id} Overhead Cam
            </div>
          </div>
        </div>

        {/* 2-Column Monitoring Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Video Feed & Proctor Controls (2 cols) */}
          <div className="lg:col-span-2 space-y-4">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Camera className="h-4 w-4 text-indigo-400" />
                  <span className="text-xs font-semibold text-white">
                    Live Video Feed — {room?.name}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] bg-red-600/20 text-red-400 border border-red-500/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-ping"></span>
                    LIVE STREAM
                  </span>
                </div>
              </div>

              {/* Authenticated MJPEG Feed */}
              <div className="relative aspect-video w-full rounded-xl overflow-hidden bg-slate-950 border border-slate-800 flex items-center justify-center">
                {/* Image element with authenticated token query parameter */}
                <img
                  src={getVideoFeedUrl(token)}
                  alt="Live Camera Feed"
                  className="w-full h-full object-contain"
                />

                {/* Overlaid status badge */}
                <div className="absolute top-3 left-3 bg-black/70 backdrop-blur-md px-3 py-1 rounded-lg border border-white/10 text-[11px] text-white flex items-center gap-2">
                  <span className="text-emerald-400">●</span>
                  <span>{room?.name}</span>
                  <span className="text-slate-400">|</span>
                  <span className="text-slate-300">{tracks.length} Detected Student(s)</span>
                </div>
              </div>

              {/* Exam Controls */}
              <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-3">
                <div className="text-xs text-slate-400">
                  Status: <span className="text-white font-semibold capitalize">{examStatus}</span>
                  {pauseReason && <span className="text-amber-400 ml-1">({pauseReason})</span>}
                </div>

                <div className="flex items-center gap-2">
                  {examStatus === 'running' ? (
                    <button
                      onClick={handlePause}
                      className="flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 transition-all cursor-pointer"
                    >
                      <Pause className="h-3.5 w-3.5" />
                      <span>Pause Exam / إيقاف مؤقت</span>
                    </button>
                  ) : (
                    <button
                      onClick={handleResume}
                      className="flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 transition-all cursor-pointer"
                    >
                      <Play className="h-3.5 w-3.5" />
                      <span>Resume Exam / استئناف</span>
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Live Student Tracking Cards */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-xl">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                <Users className="h-3.5 w-3.5 text-indigo-400" />
                <span>Active Tracked Students ({tracks.length})</span>
              </h2>

              {tracks.length === 0 ? (
                <div className="text-center py-6 text-xs text-slate-500">
                  No active student tracks currently detected in camera view.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {tracks.map((t) => (
                    <div
                      key={t.track_id}
                      className={`rounded-xl border p-3 text-xs transition-all ${
                        t.is_suspicious || t.score >= 10
                          ? 'border-red-500/40 bg-red-500/10'
                          : 'border-slate-800 bg-slate-800/40'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-bold text-white">Student #{t.track_id}</span>
                        <span
                          className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                            t.is_suspicious || t.score >= 10
                              ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                              : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          }`}
                        >
                          Score: {t.score.toFixed(1)}
                        </span>
                      </div>

                      <div className="space-y-1 text-[11px] text-slate-400">
                        <div className="flex justify-between">
                          <span>Gaze:</span>
                          <span className="text-slate-200">{t.gaze_direction}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Head Yaw / Pitch:</span>
                          <span className="text-slate-200">{t.head_yaw.toFixed(1)}° / {t.head_pitch.toFixed(1)}°</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Zone:</span>
                          <span className="text-slate-200 capitalize">{t.zone_status}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Real-Time Violation Alerts Feed (1 col) */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-xl flex flex-col h-[750px]">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-red-400" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-white">
                  Real-Time Alerts Feed
                </h2>
              </div>
              <span className="text-[10px] text-slate-500">{allEvents.length} events</span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {allEvents.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center text-xs text-slate-500">
                  <CheckCircle2 className="h-8 w-8 text-slate-700 mb-2" />
                  <span>No violations recorded yet. Room is calm.</span>
                </div>
              ) : (
                allEvents.map((ev, idx) => (
                  <div
                    key={`${ev.id}-${idx}`}
                    className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs space-y-2 hover:border-slate-700 transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-red-400 capitalize">
                        {ev.event_type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-[10px] text-slate-500 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>Target: Student #{ev.track_id ?? 'Unknown'}</span>
                      <span className="text-amber-400 font-semibold">+{ev.points} pts</span>
                    </div>

                    {ev.evidence_url && (
                      <button
                        onClick={() => setSelectedEvidence(ev.evidence_url || null)}
                        className="w-full flex items-center justify-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 py-1.5 text-[11px] font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition-all cursor-pointer"
                      >
                        <ImageIcon className="h-3 w-3 text-indigo-400" />
                        <span>View Evidence Snapshot</span>
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Modal: Evidence Snapshot */}
      {selectedEvidence && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-2xl">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-white">Violation Evidence Snapshot</h3>
              <button
                onClick={() => setSelectedEvidence(null)}
                className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded-lg border border-slate-700"
              >
                Close
              </button>
            </div>
            <div className="rounded-xl overflow-hidden bg-black border border-slate-800 aspect-video flex items-center justify-center">
              <img
                src={selectedEvidence}
                alt="Violation Evidence"
                className="w-full h-full object-contain"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
