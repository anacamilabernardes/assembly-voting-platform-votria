import type { Run } from '../App';
import { api } from '../api';
import { useI18n, type MessageKey } from '../i18n';
import type { AgendaItem, AssemblyData, AssemblySummary, Config, Me } from '../types';
import { BallotPanel } from './BallotPanel';
import { ChairPanel, FloorPanel, MinutesPanel, NewDemoPanel, ProxyPanel } from './SidePanels';

interface Props {
  me: Me;
  config: Config | null;
  data: AssemblyData | null;
  assemblies: AssemblySummary[];
  selected: string;
  onSelect: (id: string) => void;
  onSwitchPerson: (memberId: string, password: string) => void;
  run: Run;
  busy: boolean;
}

export function ruleLabel(item: Pick<AgendaItem, 'rule' | 'voting_mode'>, t: (k: MessageKey) => string) {
  const rule =
    item.rule === 'ELECTION' ? t('agenda.election') : item.rule === 'SPECIAL' ? t('agenda.special') : t('agenda.simple');
  return `${rule} · ${item.voting_mode === 'SECRET' ? t('agenda.secret') : t('agenda.nominal')}`;
}

export function AssemblyView({ me, config, data: a, assemblies, selected, onSelect, onSwitchPerson, run, busy }: Props) {
  const { t } = useI18n();
  if (!assemblies.length) {
    return (
      <main className="workspace">
        <p className="card">{t('assembly.none')}</p>
      </main>
    );
  }
  const president = !!a && me.id === a.president;
  const path = (suffix: string) => `/assemblies/${selected}${suffix}`;
  const role = president ? t('header.chair') : me.is_admin ? t('header.admin') : t('header.member');
  return (
    <main className="workspace">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">
            {a?.organization ? a.organization.toUpperCase() + ' · ' : ''}
            {t('assembly.eyebrow')}
          </p>
          <h1>{a?.title || t('assembly.loading')}</h1>
          {a && (
            <p className="muted">
              {a.code} <span className="separator">/</span> {t(`state.${a.state}` as MessageKey)}
            </p>
          )}
        </div>
        <div className="identity">
          <strong>{me.name}</strong>
          <span>{role}</span>
        </div>
      </div>
      <div className="switcher">
        {assemblies.length > 1 && (
          <>
            <label htmlFor="assembly-switch">{t('assembly.choose')}</label>
            <select id="assembly-switch" value={selected} disabled={busy} onChange={(e) => onSelect(e.target.value)}>
              {assemblies.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.code} · {x.title}
                </option>
              ))}
            </select>
          </>
        )}
        {config?.demo && me.authentication_kind === 'DEMO' && (
          <>
            <label htmlFor="identity-switch">{t('switch.label')}</label>
            <select id="identity-switch" value={me.id} disabled={busy} onChange={(e) => onSwitchPerson(e.target.value, '')}>
              {config.demo_accounts
                .filter((m) => m.organization === me.organization)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
            </select>
            <small>{t('switch.help')}</small>
          </>
        )}
      </div>
      {a && (
        <>
          <section className="summary-grid">
            <div className="metric">
              <span>{t('metric.present')}</span>
              <strong>
                {a.quorum.present}
                <small> / {a.quorum.eligible}</small>
              </strong>
              <p>{t('metric.presentHelp')}</p>
            </div>
            <div className="metric">
              <span>{t('metric.firstCall')}</span>
              <strong>{a.quorum.required}</strong>
              <p>{t('metric.firstCallHelp')}</p>
            </div>
            <div className="metric">
              <span>{t('metric.represented')}</span>
              <strong>{a.quorum.represented}</strong>
              <p>{t('metric.representedHelp')}</p>
            </div>
            <div className="metric presence">
              <span>{t('metric.mine')}</span>
              <strong className="presence-label">{a.presence.present ? t('presence.yes') : t('presence.no')}</strong>
              <button
                disabled={busy || a.state === 'CLOSED'}
                onClick={() =>
                  run(
                    () =>
                      a.presence.present
                        ? api(path('/presence/check-out'), {})
                        : api(path('/presence/check-in'), { confirmed: true }),
                    a.presence.present ? t('presence.out') : t('presence.in'),
                  )
                }
              >
                {a.presence.present ? t('presence.checkOut') : t('presence.checkIn')}
              </button>
            </div>
          </section>
          <div className="columns">
            <div className="main-column">
              <section className="card">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">{t('agenda.eyebrow')}</p>
                    <h2>{t('agenda.title')}</h2>
                  </div>
                  <span className="pill">{t('agenda.count', { n: a.agenda.length })}</span>
                </div>
                <div className="agenda">
                  {a.agenda.map((i) => (
                    <article key={i.id}>
                      <span className="agenda-number">{String(i.position).padStart(2, '0')}</span>
                      <div>
                        <h3>{i.title}</h3>
                        <p>{i.body}</p>
                        {i.options.length > 0 && (
                          <ul className="options-list">
                            {i.options.map((o) => (
                              <li key={o.id}>{o.label}</li>
                            ))}
                          </ul>
                        )}
                        <span className="rule-note">{ruleLabel(i, t)}</span>
                      </div>
                      {president && (
                        <button
                          disabled={
                            busy || a.state !== 'INSTALLED' || a.round?.state === 'OPEN' || i.voted || i.rule === 'SPECIAL'
                          }
                          onClick={() =>
                            run(() => api(path(`/agenda/${i.id}/open`), { duration_seconds: 300 }), t('agenda.opened'))
                          }
                        >
                          {i.voted ? t('agenda.voted') : i.rule === 'SPECIAL' ? t('agenda.blocked') : t('agenda.open')}
                        </button>
                      )}
                    </article>
                  ))}
                </div>
              </section>
              {a.round && <BallotPanel round={a.round} president={president} path={path} run={run} busy={busy} />}
              <section className="card media-placeholder">
                <span className="media-symbol" aria-hidden="true">
                  ◉
                </span>
                <div>
                  <h3>{t('media.title')}</h3>
                  <p>{t('media.text')}</p>
                </div>
                <span className="pill">{t('media.pending')}</span>
              </section>
            </div>
            <aside>
              {a.state === 'CLOSED' && <NewDemoPanel a={a} president={president} path={path} run={run} busy={busy} />}
              {president && <ChairPanel a={a} path={path} run={run} busy={busy} />}
              <FloorPanel a={a} me={me} president={president} path={path} run={run} busy={busy} />
              <ProxyPanel a={a} me={me} selected={selected} path={path} run={run} busy={busy} />
              {a.state === 'CLOSED' && <MinutesPanel path={path} run={run} busy={busy} />}
            </aside>
          </div>
        </>
      )}
    </main>
  );
}
