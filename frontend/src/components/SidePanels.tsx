import { useState } from 'react';
import type { Run } from '../App';
import { api } from '../api';
import { useI18n, type MessageKey } from '../i18n';
import type { AssemblyData, InboxMessage, Me } from '../types';

interface Base {
  path: (suffix: string) => string;
  run: Run;
  busy: boolean;
}

export function NewDemoPanel({ a, president, path, run, busy }: Base & { a: AssemblyData; president: boolean }) {
  const { t } = useI18n();
  if (!a.code.startsWith('SIM-')) return null;
  return (
    <section className="card">
      <p className="eyebrow">{t('newDemo.eyebrow')}</p>
      <h2>{t('newDemo.title')}</h2>
      <p>{t('newDemo.text')}</p>
      {president ? (
        <>
          <p className="muted">{t('newDemo.chair')}</p>
          <button
            className="primary full"
            disabled={busy}
            onClick={() => {
              if (window.confirm(t('newDemo.confirm')))
                run(() => api(path('/new-demo'), { confirmed: true }), t('newDemo.started'));
            }}
          >
            {t('newDemo.button')}
          </button>
        </>
      ) : (
        <p className="muted">{t('newDemo.wait')}</p>
      )}
    </section>
  );
}

export function ChairPanel({ a, path, run, busy }: Base & { a: AssemblyData }) {
  const { t } = useI18n();
  return (
    <section className="card">
      <p className="eyebrow">{t('chair.eyebrow')}</p>
      <h2>{t('chair.title')}</h2>
      {a.state === 'PUBLISHED' ? (
        <>
          <p>{t('chair.proxyWindow')}</p>
          <button
            className="primary full"
            disabled={busy}
            onClick={() => run(() => api(path('/install'), { call: 1 }), t('chair.installedMsg'))}
          >
            {t('chair.first')}
          </button>
          <button
            className="full"
            disabled={busy}
            onClick={() => run(() => api(path('/install'), { call: 2 }), t('chair.installedMsg'))}
          >
            {t('chair.second')}
          </button>
        </>
      ) : (
        <p className="muted">
          {t('chair.installed', { call: a.installation.call ?? '', present: a.installation.present ?? '' })}
        </p>
      )}
      {a.state === 'INSTALLED' && (
        <button
          className="outline full"
          disabled={busy || a.round?.state === 'OPEN'}
          onClick={() => {
            if (window.confirm(t('chair.finishConfirm'))) run(() => api(path('/close'), {}), t('chair.finished'));
          }}
        >
          {t('chair.finish')}
        </button>
      )}
    </section>
  );
}

export function FloorPanel({ a, me, president, path, run, busy }: Base & { a: AssemblyData; me: Me; president: boolean }) {
  const { t } = useI18n();
  const mine = a.floor.find((f) => f.member_id === me.id);
  const canAsk = !busy && a.presence.present && a.state === 'INSTALLED' && !mine;
  return (
    <section className="card">
      <div className="section-heading">
        <h2>{t('floor.title')}</h2>
        <span className="pill">{a.floor.length}</span>
      </div>
      <div className="stack">
        <button disabled={!canAsk} onClick={() => run(() => api(path('/floor'), { kind: 'NORMAL' }), t('floor.updated'))}>
          {t('floor.raise')}
        </button>
        <button disabled={!canAsk} onClick={() => run(() => api(path('/floor'), { kind: 'ORDER' }), t('floor.updated'))}>
          {t('floor.order')}
        </button>
        {mine && (
          <button
            disabled={busy}
            onClick={() => run(() => api(path(`/floor/${mine.id}/decision`), { decision: 'WITHDRAW' }), t('floor.updated'))}
          >
            {t('floor.withdraw')}
          </button>
        )}
      </div>
      {a.floor.length === 0 ? (
        <p className="muted">{t('floor.empty')}</p>
      ) : (
        <ol className="floor-list">
          {a.floor.map((f) => (
            <li key={f.id}>
              <strong>{f.name}</strong>
              <small>
                {f.kind === 'ORDER' ? t('floor.kindOrder') : t('floor.kindNormal')} ·{' '}
                {f.state === 'GRANTED' ? t('floor.speaking') : t('floor.waiting')}
              </small>
              {president && (
                <button
                  disabled={busy}
                  onClick={() =>
                    run(
                      () => api(path(`/floor/${f.id}/decision`), { decision: f.state === 'GRANTED' ? 'END' : 'GRANT' }),
                      t('floor.updated'),
                    )
                  }
                >
                  {f.state === 'GRANTED' ? t('floor.end') : t('floor.grant')}
                </button>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function ProxyPanel({ a, me, selected, path, run, busy }: Base & { a: AssemblyData; me: Me; selected: string }) {
  const { t } = useI18n();
  const [representative, setRepresentative] = useState('');
  const [code, setCode] = useState('');
  const [inbox, setInbox] = useState<InboxMessage[]>([]);
  return (
    <section className="card">
      <p className="eyebrow">{t('proxy.eyebrow')}</p>
      <h2>{t('proxy.title')}</h2>
      <p className="muted">{t('proxy.help')}</p>
      {a.proxies.map((p) => (
        <div key={p.id} className="proxy-row">
          <strong>
            {p.grantor} → {p.representative}
          </strong>
          <small>{t(`condition.${p.condition}` as MessageKey)}</small>
          {p.grantor_id === me.id && ['ISSUED', 'ACCEPTED'].includes(p.status) && a.state !== 'CLOSED' && (
            <button disabled={busy} onClick={() => run(() => api(path(`/proxies/${p.id}/revoke`), {}), t('proxy.revoked'))}>
              {t('proxy.revoke')}
            </button>
          )}
        </div>
      ))}
      {a.state === 'PUBLISHED' && (
        <>
          <label htmlFor="representative">{t('proxy.grantTo')}</label>
          <select id="representative" value={representative} onChange={(e) => setRepresentative(e.target.value)}>
            <option value="">{t('proxy.choose')}</option>
            {a.members
              .filter((m) => m.id !== me.id)
              .map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
          </select>
          <button
            className="full"
            disabled={busy || !representative}
            onClick={() => {
              if (window.confirm(t('proxy.grantConfirm')))
                run(
                  () =>
                    api(path('/proxies'), {
                      representative_id: representative,
                      scope: a.agenda.map((i) => i.id),
                      confirmed: true,
                    }),
                  t('proxy.granted'),
                );
            }}
          >
            {t('proxy.grant')}
          </button>
          <label htmlFor="proxy-code">{t('proxy.code')}</label>
          <input
            id="proxy-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder={t('proxy.codePlaceholder')}
            autoComplete="off"
          />
          <button
            className="full"
            disabled={busy || !code}
            onClick={() =>
              run(async () => {
                await api(path('/proxies/claim'), { code });
                setCode('');
              }, t('proxy.accepted'))
            }
          >
            {t('proxy.accept')}
          </button>
          {me.authentication_kind === 'DEMO' && (
            <button
              className="text-button"
              disabled={busy}
              onClick={() => run(async () => setInbox(await api<InboxMessage[]>(`/demo/inbox?assembly_id=${selected}`)))}
            >
              {t('proxy.inbox')}
            </button>
          )}
          {inbox.map((m) => (
            <div className="inbox" key={m.id}>
              <small>
                {m.subject} · {t('proxy.inboxNote')}
              </small>
              <code>{m.code}</code>
            </div>
          ))}
        </>
      )}
    </section>
  );
}

export function MinutesPanel({ path, run, busy }: Base) {
  const { t } = useI18n();
  async function download() {
    const minutes = await api<unknown>(path('/minutes'));
    const url = URL.createObjectURL(new Blob([JSON.stringify(minutes, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'votria-minutes.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <section className="card">
      <p className="eyebrow">{t('minutes.eyebrow')}</p>
      <h2>{t('minutes.title')}</h2>
      <p>{t('minutes.text')}</p>
      <a className="button primary full" href={'/api/v1' + path('/minutes.html')} target="_blank" rel="noopener">
        {t('minutes.read')}
      </a>
      <button className="full" disabled={busy} onClick={() => run(download)}>
        {t('minutes.json')}
      </button>
    </section>
  );
}
