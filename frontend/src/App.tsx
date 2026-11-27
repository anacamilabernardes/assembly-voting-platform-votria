import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import { AdminView } from './components/AdminView';
import { AssemblyView } from './components/AssemblyView';
import { Header } from './components/Header';
import { Login } from './components/Login';
import { PrivacyNotice } from './components/PrivacyNotice';
import { useI18n } from './i18n';
import type { AssemblyData, AssemblySummary, Config, Me } from './types';

export type View = 'assembly' | 'admin' | 'privacy';
export type Run = (action: () => Promise<unknown>, message?: string | (() => string)) => Promise<void>;

export function App() {
  const { t, errorText } = useI18n();
  const [config, setConfig] = useState<Config | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [assemblies, setAssemblies] = useState<AssemblySummary[]>([]);
  const [selected, setSelected] = useState('');
  const [data, setData] = useState<AssemblyData | null>(null);
  const [view, setView] = useState<View>('assembly');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  function changeView(next: View) {
    setView(next);
    setError('');
    setNotice('');
  }

  const loadAssembly = useCallback(
    async (id: string) => {
      if (!id) return;
      const state = await api<AssemblyData>(`/assemblies/${id}/state`);
      if (state.next_demo_id) {
        setSelected(state.next_demo_id);
        setData(await api<AssemblyData>(`/assemblies/${state.next_demo_id}/state`));
        setNotice(t('newDemo.started'));
      } else {
        setData(state);
      }
    },
    [t],
  );

  const loadSession = useCallback(async () => {
    const cfg = await api<Config>('/config');
    setConfig(cfg);
    if (!cfg.authenticated) {
      setMe(null);
      setData(null);
      return;
    }
    try {
      const person = await api<Me>('/me');
      setMe(person);
      const list = await api<AssemblySummary[]>('/assemblies');
      setAssemblies(list);
      const first = list[0]?.id ?? '';
      setSelected(first);
      setData(first ? await api<AssemblyData>(`/assemblies/${first}/state`) : null);
    } catch {
      setMe(null);
      setData(null);
    }
  }, []);

  useEffect(() => {
    loadSession().catch((e) => setError(errorText(e)));
  }, [loadSession, errorText]);

  useEffect(() => {
    if (!me || !selected || view !== 'assembly') return;
    const timer = setInterval(() => loadAssembly(selected).catch((e) => setError(errorText(e))), 5000);
    return () => clearInterval(timer);
  }, [me, selected, view, loadAssembly, errorText]);

  const sessionId = data?.presence.session_id;
  useEffect(() => {
    if (!sessionId || !selected) return;
    const timer = setInterval(
      () => api(`/assemblies/${selected}/presence/heartbeat`, { session_id: sessionId }).catch((e) => setError(errorText(e))),
      15000,
    );
    return () => clearInterval(timer);
  }, [sessionId, selected, errorText]);

  const run: Run = async (action, message) => {
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
      if (view === 'assembly' && selected) await loadAssembly(selected);
      setNotice(typeof message === 'function' ? message() : (message ?? t('ok')));
    } catch (e) {
      setError(errorText(e));
      if (view === 'assembly' && selected) await loadAssembly(selected).catch(() => undefined);
    } finally {
      setBusy(false);
    }
  };

  async function signIn(memberId: string, password: string) {
    setBusy(true);
    setError('');
    setNotice('');
    setData(null);
    try {
      await api('/auth/demo', { member_id: memberId, access_password: password });
      setView('assembly');
      await loadSession();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    await run(async () => {
      await api('/auth/logout', {});
      setMe(null);
      setData(null);
      setSelected('');
      setAssemblies([]);
    }, t('header.signOut'));
  }

  async function choose(id: string) {
    setSelected(id);
    setData(null);
    await loadAssembly(id).catch((e) => setError(errorText(e)));
  }

  async function afterPublish() {
    setAssemblies(await api<AssemblySummary[]>('/assemblies'));
  }

  return (
    <div className="app">
      <Header me={me} view={view} setView={changeView} onSignOut={signOut} busy={busy} />
      <div className="demo-banner">
        <span className="dot" /> {t('banner.title')} <span>{t('banner.text')}</span>
      </div>
      {error && (
        <div className="message error" role="alert">
          {error}
          <button onClick={() => setError('')} aria-label="×">
            ×
          </button>
        </div>
      )}
      {notice && (
        <div className="message success" role="status">
          {notice}
        </div>
      )}
      {view === 'privacy' ? (
        <PrivacyNotice organization={me?.organization || config?.institution_name || 'Votria'} />
      ) : !me ? (
        config && <Login config={config} busy={busy} onChoose={signIn} />
      ) : view === 'admin' && me.is_admin ? (
        <AdminView run={run} busy={busy} onPublished={afterPublish} />
      ) : (
        <AssemblyView
          me={me}
          config={config}
          data={data}
          assemblies={assemblies}
          selected={selected}
          onSelect={choose}
          onSwitchPerson={signIn}
          run={run}
          busy={busy}
        />
      )}
      <footer>
        <span>{t('footer.left')}</span>
        <span>{t('footer.middle')}</span>
        <span>{t('footer.right')}</span>
      </footer>
    </div>
  );
}
