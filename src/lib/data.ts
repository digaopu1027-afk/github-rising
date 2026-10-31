import fs from 'node:fs';
import path from 'node:path';

export interface Evidence { quote: string; url: string }
export interface Project {
  id: number; full_name: string; name: string; description: string;
  url: string; homepage: string | null; stars: number; forks: number;
  language: string | null; license: string; pushed_at: string | null;
  created_at: string; sampled_at: string; category: string; kind: string;
  summary_zh: string | null; audience_zh: string | null;
  evidence: Evidence[]; content_status: string; readme_url: string;
  delta: number | null; growth_rate: number | null; rising_score: number | null;
  window_start: string | null; window_end: string; window_hours: number | null;
  observation: 'ready' | 'warming' | 'invalid_window'; rank?: number;
}
export interface Board {
  schema_version: number; date: string; generated_at: string | null;
  tracked_count: number; sampled_count: number; eligible_count: number;
  rankable_count: number; warming_count: number;
  hot: Project[]; rising: Project[]; observing: Project[]; projects: Project[];
  notes: string[]; categories: string[];
  sources: { kind: string; url: string; count: number; category?: string; period?: string }[];
}
export interface Point { date: string; sampled_at: string; stars: number; delta: number | null }
export interface Detail { repo: Project; history: Point[] }
export interface HistoryEntry {date: string; generated_at: string; sampled_count: number; eligible_count: number}

const dataRoot = path.resolve('public/data');
export function read<T>(relative: string, fallback: T): T {
  const target = path.join(dataRoot, relative);
  return fs.existsSync(target) ? JSON.parse(fs.readFileSync(target, 'utf-8')) as T : fallback;
}
export const categories = ['AI', '开发工具', '效率办公', '设计创作', '学习教育', '其他'];
const empty: Board = {schema_version: 1, date: '', generated_at: null, tracked_count: 0,
  sampled_count: 0, eligible_count: 0, rankable_count: 0, warming_count: 0,
  hot: [], rising: [], observing: [], projects: [], notes: [], categories, sources: []};
export const latest = read<Board>('latest.json', empty);
export const archives = read<HistoryEntry[]>('history/index.json', []);
export const status = read<{state: string; message?: string; attempted_at?: string}>('status.json', {state: 'pending'});
export const projectIndex = read<{id: number; full_name: string}[]>('projects/index.json', []);
export const base = import.meta.env.BASE_URL.replace(/\/$/, '');
export const href = (route = '') => `${base}/${route.replace(/^\//, '')}`;
export function number(value: number) { return value.toLocaleString('zh-CN'); }
export function shortNumber(value: number) {
  return value >= 10000 ? `${(value / 1000).toFixed(1).replace(/\.0$/, '')}k` : number(value);
}
export function dateTime(value: string | null, full = true) {
  if (!value) return '尚未采集';
  return new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai',
    month: '2-digit', day: '2-digit', ...(full ? {year: 'numeric' as const} : {}),
    hour: '2-digit', minute: '2-digit', hour12: false}).format(new Date(value));
}
export function readableDate(value: string) {
  return value ? new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', weekday: 'long'}).format(new Date(value + 'T09:00:00+08:00')) : '等待首次记录';
}
export const detailHref = (id: number, date?: string) => date ? href(`history/${date}/${id}/`) : href(`projects/${id}/`);
