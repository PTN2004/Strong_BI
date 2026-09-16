import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { buildApiUrl } from '@/config/api';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ReactECharts from 'echarts-for-react';
import { Loader2, ArrowLeft, AlertCircle, CheckCircle2 } from 'lucide-react';

/* Trang quản lý conversation:
   - Admin: xem MỌI account (lọc theo email) — full trace (SQL/Data/Chart/steps)
   - User thường mở deep-link /conversations/<id> của chính mình: thấy theo quyền */

interface ConvSummary {
  id: string; user_email: string; graph_id: string; query: string;
  status: string; intent?: string; playbook?: string;
  duration_ms?: number; created_at?: string; has_error: boolean;
}
interface ConvDetail extends ConvSummary {
  answer?: string; error?: string; steps?: string[];
  sql?: string; table_data?: any[]; chart_config?: { option?: any };
}

const fmtTime = (iso?: string) => (iso ? new Date(iso).toLocaleString('vi-VN') : '');
const fmtDur = (ms?: number) => (ms == null ? '' : ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`);

const SimpleTable = ({ data }: { data: any[] }) => {
  if (!data?.length) return null;
  const cols = Object.keys(data[0]);
  return (
    <div className="overflow-auto max-h-[380px] border rounded-xl">
      <table className="w-full text-sm text-left">
        <thead className="sticky top-0 bg-muted/80 border-b">
          <tr>{cols.map(c => <th key={c} className="px-3 py-2 font-semibold">{c}</th>)}</tr>
        </thead>
        <tbody className="divide-y">
          {data.slice(0, 200).map((row, i) => (
            <tr key={i}>{cols.map(c => (
              <td key={c} className="px-3 py-1.5 whitespace-nowrap">
                {typeof row[c] === 'number' ? new Intl.NumberFormat('en-US').format(row[c]) : String(row[c] ?? '')}
              </td>
            ))}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="space-y-2">
    <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wide">{title}</h3>
    {children}
  </div>
);

const ConversationDetail = ({ threadId }: { threadId: string }) => {
  const navigate = useNavigate();
  const [detail, setDetail] = useState<ConvDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(buildApiUrl(`/conversations/${threadId}`), { credentials: 'include' })
      .then(async r => { if (!r.ok) throw new Error((await r.json()).error || `HTTP ${r.status}`); return r.json(); })
      .then(setDetail)
      .catch(e => setErr(e.message));
  }, [threadId]);

  if (err) return <div className="p-8 text-red-500 flex items-center gap-2"><AlertCircle className="w-5 h-5" />{err}</div>;
  if (!detail) return <div className="p-8"><Loader2 className="w-6 h-6 animate-spin" /></div>;

  return (
    <div className="space-y-6 max-w-5xl">
      <Button variant="ghost" size="sm" onClick={() => navigate('/conversations')}>
        <ArrowLeft className="w-4 h-4 mr-1" /> Danh sách
      </Button>

      {/* Meta */}
      <div className="border rounded-2xl p-5 space-y-3 bg-card">
        <div className="flex items-center gap-2 flex-wrap text-sm">
          {detail.has_error
            ? <span className="flex items-center gap-1 text-red-500 font-semibold"><AlertCircle className="w-4 h-4" />ERROR</span>
            : <span className="flex items-center gap-1 text-green-600 font-semibold"><CheckCircle2 className="w-4 h-4" />DONE</span>}
          <span className="px-2 py-0.5 bg-muted rounded-md">{detail.user_email}</span>
          <span className="px-2 py-0.5 bg-muted rounded-md">graph: {detail.graph_id}</span>
          {detail.intent && <span className="px-2 py-0.5 bg-blue-50 text-blue-700 dark:bg-blue-950 rounded-md">intent: {detail.intent}</span>}
          {detail.playbook && <span className="px-2 py-0.5 bg-purple-50 text-purple-700 dark:bg-purple-950 rounded-md">📘 {detail.playbook}</span>}
          <span className="text-muted-foreground">{fmtTime(detail.created_at)} · {fmtDur(detail.duration_ms)}</span>
        </div>
        <div className="text-base font-semibold">“{detail.query}”</div>
      </div>

      {detail.error && (
        <Section title="Lỗi">
          <pre className="bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 p-4 rounded-xl text-xs whitespace-pre-wrap">{detail.error}</pre>
        </Section>
      )}

      {detail.steps && detail.steps.length > 0 && (
        <Section title={`Trace (${detail.steps.length} bước)`}>
          <ol className="space-y-1 text-sm border rounded-xl p-4 bg-card">
            {detail.steps.map((s, i) => <li key={i} className="text-muted-foreground">{s}</li>)}
          </ol>
        </Section>
      )}

      {detail.sql && (
        <Section title="SQL">
          <pre className="bg-gray-950 text-amber-200 p-4 rounded-xl text-xs overflow-auto">{detail.sql}</pre>
        </Section>
      )}

      {detail.table_data && detail.table_data.length > 0 && (
        <Section title={`Data (${detail.table_data.length} dòng)`}>
          <SimpleTable data={detail.table_data} />
        </Section>
      )}

      {detail.chart_config?.option && (
        <Section title="Chart">
          <div className="border rounded-xl p-3"><ReactECharts option={detail.chart_config.option} style={{ height: 380 }} opts={{ renderer: 'svg' }} /></div>
        </Section>
      )}

      {detail.answer && (
        <Section title="Câu trả lời user nhận được">
          <div className="border rounded-xl p-5 bg-card [&_ul]:list-disc [&_ul]:pl-5 [&_p]:my-2 [&_strong]:font-semibold">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{detail.answer}</ReactMarkdown>
          </div>
        </Section>
      )}
    </div>
  );
};

const ConversationList = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = (user?.role || '').toLowerCase() === 'admin';
  const [items, setItems] = useState<ConvSummary[]>([]);
  const [emailFilter, setEmailFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const load = (email?: string) => {
    setLoading(true);
    const qs = email ? `?user_email=${encodeURIComponent(email)}` : '';
    fetch(buildApiUrl(`/conversations${qs}`), { credentials: 'include' })
      .then(r => r.json())
      .then(d => setItems(d.conversations || []))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-bold flex-1">Conversations {isAdmin ? '(tất cả tài khoản)' : '(của bạn)'}</h2>
        {isAdmin && (
          <>
            <Input placeholder="Lọc theo email…" value={emailFilter}
              onChange={e => setEmailFilter(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && load(emailFilter.trim() || undefined)}
              className="w-64" />
            <Button size="sm" onClick={() => load(emailFilter.trim() || undefined)}>Lọc</Button>
          </>
        )}
      </div>
      {loading ? <Loader2 className="w-6 h-6 animate-spin" /> : (
        <div className="border rounded-2xl divide-y bg-card">
          {items.length === 0 && <div className="p-6 text-muted-foreground text-sm">Chưa có conversation nào.</div>}
          {items.map(c => (
            <button key={c.id} onClick={() => navigate(`/conversations/${c.id}`)}
              className="w-full text-left p-4 hover:bg-muted/40 transition-colors flex items-center gap-3">
              {c.has_error
                ? <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
                : <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0" />}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{c.query}</div>
                <div className="text-xs text-muted-foreground">
                  {c.user_email} · {c.graph_id} · {c.intent}{c.playbook ? ` · 📘 ${c.playbook}` : ''} · {fmtTime(c.created_at)} · {fmtDur(c.duration_ms)}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const V4Conversations = () => {
  const { threadId } = useParams();
  return (
    <div className="p-6 overflow-y-auto h-full">
      {threadId ? <ConversationDetail threadId={threadId} /> : <ConversationList />}
    </div>
  );
};

export default V4Conversations;
