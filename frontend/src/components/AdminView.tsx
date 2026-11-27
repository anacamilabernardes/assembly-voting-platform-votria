import { useCallback, useEffect, useState, type FormEvent } from 'react';
import type { Run } from '../App';
import { ApiError, api } from '../api';
import { useI18n, type MessageKey } from '../i18n';
import type { DraftDetail, ImportError, Organization, RuleKind, VotingMode } from '../types';
import { ruleLabel } from './AssemblyView';

interface Props {
  run: Run;
  busy: boolean;
  onPublished: () => Promise<void>;
}

const local = (offsetMinutes: number) => {
  const d = new Date(Date.now() + offsetMinutes * 60000);
  d.setSeconds(0, 0);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

export function AdminView({ run, busy, onPublished }: Props) {
  const { t, errorText } = useI18n();
  const [org, setOrg] = useState<Organization | null>(null);
  const [draftId, setDraftId] = useState('');
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [importErrors, setImportErrors] = useState<ImportError[]>([]);
  const [loadError, setLoadError] = useState('');

  const load = useCallback(async () => {
    setOrg(await api<Organization>('/admin/organization'));
  }, []);
  const loadDraft = useCallback(async (id: string) => {
    setDraft(id ? await api<DraftDetail>(`/admin/assemblies/${id}`) : null);
  }, []);

  useEffect(() => {
    load().catch((e) => setLoadError(errorText(e)));
  }, [load, errorText]);
  useEffect(() => {
    loadDraft(draftId).catch((e) => setLoadError(errorText(e)));
  }, [draftId, loadDraft, errorText]);

  if (!org) return <main className="workspace">{loadError && <p className="card">{loadError}</p>}</main>;

  async function importCsv(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const file = form.get('csv') as File | null;
    if (!file || !file.size) return;
    const text = await file.text();
    setImportErrors([]);
    let summary = { created: 0, updated: 0 };
    await run(
      async () => {
        try {
          summary = await api('/admin/members/import', { csv: text, simulation: form.get('simulation') === 'on' });
        } catch (error) {
          if (error instanceof ApiError && Array.isArray(error.detail)) setImportErrors(error.detail);
          throw error;
        }
        await load();
      },
      () => t('admin.imported', summary),
    );
  }

  async function createAssembly(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const iso = (name: string) => new Date(String(f.get(name))).toISOString();
    await run(async () => {
      const created = await api<{ id: string }>('/admin/assemblies', {
        title: f.get('title'),
        first_call_at: iso('first_call_at'),
        second_call_at: iso('second_call_at'),
        president_id: f.get('president_id'),
        secretary_id: f.get('secretary_id'),
      });
      await load();
      setDraftId(created.id);
    }, t('admin.created'));
  }

  return (
    <main className="workspace">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">{t('admin.eyebrow')}</p>
          <h1>{org.name}</h1>
          <p className="muted">{t('admin.membersCount', { n: org.members.length, domain: org.email_domain })}</p>
        </div>
      </div>
      <div className="columns">
        <div className="main-column">
          <section className="card">
            <h2>{t('admin.assemblies')}</h2>
            <div className="table-wrap">
              <table>
                <tbody>
                  {org.assemblies.map((x) => (
                    <tr key={x.id}>
                      <td>{x.code}</td>
                      <td>{x.title}</td>
                      <td>{t(`state.${x.state}` as MessageKey)}</td>
                      <td>
                        {x.state === 'DRAFT' && (
                          <button className="small" onClick={() => setDraftId(x.id)}>
                            {t('admin.edit')}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {draft ? (
            <DraftEditor
              draft={draft}
              run={run}
              busy={busy}
              reload={() => loadDraft(draft.id)}
              onPublished={async () => {
                setDraftId('');
                await load();
                await onPublished();
              }}
            />
          ) : (
            <p className="muted">{t('admin.noDraft')}</p>
          )}
          <section className="card">
            <h2>{t('admin.members')}</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t('admin.col.name')}</th>
                    <th>{t('admin.col.number')}</th>
                    <th>E-mail</th>
                    <th>{t('admin.col.vote')}</th>
                    <th>{t('admin.col.kind')}</th>
                  </tr>
                </thead>
                <tbody>
                  {org.members.map((m) => (
                    <tr key={m.id}>
                      <td>
                        {m.name}
                        {m.is_admin && <span className="pill inline">admin</span>}
                      </td>
                      <td>{m.number}</td>
                      <td>{m.email}</td>
                      <td>{m.can_vote ? t('admin.yes') : t('admin.no')}</td>
                      <td>
                        {m.simulation
                          ? t('admin.kind.simulation')
                          : m.identity_linked
                            ? t('admin.kind.linked')
                            : t('admin.kind.pending')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
        <aside>
          <section className="card">
            <h2>{t('admin.new')}</h2>
            <form onSubmit={createAssembly}>
              <label htmlFor="title">{t('admin.titleField')}</label>
              <input id="title" name="title" required maxLength={250} />
              <label htmlFor="first_call_at">{t('admin.firstCall')}</label>
              <input id="first_call_at" name="first_call_at" type="datetime-local" required defaultValue={local(-30)} />
              <label htmlFor="second_call_at">{t('admin.secondCall')}</label>
              <input id="second_call_at" name="second_call_at" type="datetime-local" required defaultValue={local(-5)} />
              {(['president_id', 'secretary_id'] as const).map((field) => (
                <div key={field}>
                  <label htmlFor={field}>{field === 'president_id' ? t('admin.president') : t('admin.secretary')}</label>
                  <select id={field} name={field} required defaultValue="">
                    <option value="" disabled>
                      {t('admin.choose')}
                    </option>
                    {org.members.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
              <button className="primary full" disabled={busy} type="submit">
                {t('admin.create')}
              </button>
            </form>
          </section>
          <section className="card">
            <h2>{t('admin.import')}</h2>
            <p className="muted">{t('admin.importHelp')}</p>
            <form onSubmit={importCsv}>
              <label htmlFor="csv">{t('admin.file')}</label>
              <input id="csv" name="csv" type="file" accept=".csv,text/csv" required />
              <label className="checkbox">
                <input type="checkbox" name="simulation" defaultChecked /> {t('admin.simulation')}
              </label>
              <button className="primary full" disabled={busy} type="submit">
                {t('admin.importButton')}
              </button>
            </form>
            {importErrors.length > 0 && (
              <div className="import-errors" role="alert">
                <p>{t('admin.importErrors')}</p>
                <ul>
                  {importErrors.map((e, i) => (
                    <li key={i}>{t('admin.line', { line: e.line, error: e.error })}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}

function DraftEditor({
  draft,
  run,
  busy,
  reload,
  onPublished,
}: {
  draft: DraftDetail;
  run: Run;
  busy: boolean;
  reload: () => Promise<void>;
  onPublished: () => Promise<void>;
}) {
  const { t } = useI18n();
  const [kind, setKind] = useState<RuleKind>('SIMPLE');
  const [mode, setMode] = useState<VotingMode>('NOMINAL');
  const base = `/admin/assemblies/${draft.id}`;

  async function addItem(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const options = String(f.get('options') ?? '')
      .split('\n')
      .map((o) => o.trim())
      .filter(Boolean);
    await run(async () => {
      await api(base + '/agenda', {
        title: f.get('title'),
        body: f.get('body'),
        rule_kind: kind,
        voting_mode: kind === 'ELECTION' ? 'SECRET' : mode,
        ...(kind === 'ELECTION' ? { options } : {}),
      });
      form.reset();
      setKind('SIMPLE');
      setMode('NOMINAL');
      await reload();
    }, t('admin.itemAdded'));
  }

  return (
    <section className="card">
      <p className="eyebrow">{t('admin.draftOf', { code: draft.code })}</p>
      <h2>{draft.title}</h2>
      <p className="muted">
        {t('admin.president')}: {draft.president.name} · {t('admin.secretary')}: {draft.secretary.name}
      </p>
      <div className="agenda">
        {draft.agenda.map((i) => (
          <article key={i.id}>
            <span className="agenda-number">{String(i.position).padStart(2, '0')}</span>
            <div>
              <h3>{i.title}</h3>
              <p>{i.body}</p>
              {i.options.length > 0 && (
                <ul className="options-list">
                  {i.options.map((o) => (
                    <li key={o}>{o}</li>
                  ))}
                </ul>
              )}
              <span className="rule-note">{ruleLabel(i, t)}</span>
            </div>
            <button
              disabled={busy}
              onClick={() =>
                run(async () => {
                  await api(`${base}/agenda/${i.id}/remove`, {});
                  await reload();
                })
              }
            >
              {t('admin.remove')}
            </button>
          </article>
        ))}
      </div>
      <form onSubmit={addItem} className="item-form">
        <h3>{t('admin.addItem')}</h3>
        <label htmlFor="item-title">{t('admin.itemTitle')}</label>
        <input id="item-title" name="title" required maxLength={250} />
        <label htmlFor="item-body">{t('admin.itemBody')}</label>
        <textarea id="item-body" name="body" required rows={3} />
        <div className="two">
          <div>
            <label htmlFor="item-kind">{t('admin.kind')}</label>
            <select id="item-kind" value={kind} onChange={(e) => setKind(e.target.value as RuleKind)}>
              {(['SIMPLE', 'ELECTION', 'SPECIAL'] as const).map((k) => (
                <option key={k} value={k}>
                  {t(`admin.kind.${k}`)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="item-mode">{t('admin.mode')}</label>
            <select
              id="item-mode"
              value={kind === 'ELECTION' ? 'SECRET' : mode}
              disabled={kind === 'ELECTION'}
              onChange={(e) => setMode(e.target.value as VotingMode)}
            >
              <option value="NOMINAL">{t('admin.mode.NOMINAL')}</option>
              <option value="SECRET">{t('admin.mode.SECRET')}</option>
            </select>
          </div>
        </div>
        {kind === 'ELECTION' && (
          <>
            <label htmlFor="item-options">{t('admin.options')}</label>
            <textarea id="item-options" name="options" required rows={3} />
          </>
        )}
        <button className="full" disabled={busy} type="submit">
          {t('admin.addItem')}
        </button>
      </form>
      <button
        className="primary full"
        disabled={busy || draft.agenda.length === 0}
        onClick={() => {
          if (!window.confirm(t('admin.publishConfirm'))) return;
          let electors = 0;
          run(
            async () => {
              const published = await api<{ electors: number }>(`${base}/publish`, {});
              electors = published.electors;
              await onPublished();
            },
            () => t('admin.published', { n: electors }),
          );
        }}
      >
        {t('admin.publish')}
      </button>
    </section>
  );
}
