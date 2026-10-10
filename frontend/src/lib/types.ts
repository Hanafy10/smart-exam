export interface User {
  id: number;
  username: string;
  email?: string;
  role: 'admin' | 'invigilator' | string;
  is_active: boolean;
  assigned_room_id?: number | null;
  assigned_room_name?: string | null;
}

export interface Camera {
  id: number;
  room_id: number;
  name: string;
  is_online: boolean;
  last_seen?: string;
}

export interface ExamRoom {
  id: number;
  name: string;
  building?: string;
  capacity: number;
  cameras: Camera[];
  invigilator_count: number;
}

export interface Invigilator {
  id: number;
  username: string;
  email?: string;
  role: string;
  is_active: boolean;
  assigned_room_id?: number | null;
  assigned_room_name?: string | null;
  created_at: string;
}

export interface RoomMonitoringSummary {
  room_id: number;
  room_name: string;
  building?: string;
  total_students: number;
  suspicious_students: number;
  total_violations: number;
  violence_detection_status: string; // 'unavailable'
  camera_online: boolean;
  is_paused: boolean;
}

export interface ViolationEvent {
  id: number;
  room_id?: number;
  camera_id?: number;
  track_id?: number;
  student_name?: string;
  student_college_id?: string;
  event_type: string;
  points: number;
  total_score?: number;
  is_suspicious?: boolean;
  is_violence?: boolean;
  severity?: string;
  evidence_url?: string;
  timestamp: string;
}

export interface StudentTrack {
  track_id: number;
  student_college_id?: string;
  student_name?: string;
  score: number;
  is_suspicious: boolean;
  presence_state: string;
  head_yaw: number;
  head_pitch: number;
  gaze_direction: string;
  gaze_baseline_h?: number;
  zone_status: string;
  events?: ViolationEvent[];
}

export interface AITrackState {
  track_id: number;
  head_yaw: number;
  head_pitch: number;
  gaze_direction: string;
  gaze_baseline_h?: number;
  zone_status: string;
  score: number;
  presence_state: string;
}

export interface ExamSession {
  id: number;
  room_id: number;
  title: string;
  status: 'running' | 'paused' | 'completed';
  pause_reason?: string;
  student_count: number;
}
