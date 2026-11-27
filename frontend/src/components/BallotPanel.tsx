import { useState } from 'react';
import type { Run } from '../App';
import { api } from '../api';
import { useI18n, type MessageKey } from '../i18n';
import type { ElectionResult, RoundState, SimpleResult } from '../types';

interface Props {
  round: RoundState;
  president: boolean;
  path: (suffix: string) => string;
  run: Run;
  busy: boolean;
}

interface Pending {
  ownerId: string;
  name: string;
  choice: string;
  label: string;
}

export function BallotPanel({ round: r, president, path, run, busy }: Props) {
  const { t, lang } = useI18n();
  const [pending, setPending] = useState<Pending | null>(null);
  const election = r.kind === 'ELECTION';
  const secret = r.voting_mode === 'SECRET';
  const choices = election
    ? [
        ...r.options.map((o) => ({ value: o.id, label: o.label, tone: 'option' })),
        { value: 'BLANK', label: t('choice.BLANK'), tone: 'abstain' },
      ]
    : (['YES', 'NO', 'ABSTAIN'] as const).map((c) => ({ value: c, label: t(`choice.${c}`), tone: c.toLowerCase() }));
  const choiceLabel = (value: string) => choices.find((c) => c.value === value)?.label ?? value;

  return (
    <section className="card ballot-panel" aria-live="polite">
      <div className="section-heading">
        <div>
          <p className="eyebrow">{r.state === 'OPEN' ? t('ballot.open') : t('ballot.closed')}</p>
          <h2>{r.title}</h2>
        </div>
        <span className="pill">{t('ballot.received', { n: r.received })}</span>
      </div>
      <p className="proposal">{r.body}</p>
      {r.state === 'OPEN' ? (
        <>
          <p className="muted">
            {t('ballot.closesAt', {
              time: new Date(r.closes_at).toLocaleTimeString(lang === 'pt' ? 'pt-BR' : 'en-GB'),
            })}
          </p>
          {secret && <p className="secret-note">{t('ballot.secretNote')}</p>}
          <div className="ballot-cards">
            {r.cards.map((c) => (
              <div className="ballot-card" key={c.owner_id}>
                <small>{c.own ? t('ballot.mine') : t('ballot.proxy')}</small>
                <h3>{c.name}</h3>
                {c.receipt ? (
                  <div className="receipt">
                    <strong>
                      {c.receipt.choice
                        ? t('ballot.confirmed', { choice: choiceLabel(c.receipt.choice) })
                        : t('ballot.secretConfirmed')}
                    </strong>
                    <span>{t('ballot.by', { name: c.receipt.executor })}</span>
                    <code>{c.receipt.protocol}</code>
                  </div>
                ) : c.available ? (
                  <div className={'choices' + (election ? ' vertical' : '')}>
                    {choices.map((choice) => (
                      <button
                        disabled={busy}
                        className={choice.tone}
                        key={choice.value}
                        onClick={() =>
                          setPending({ ownerId: c.owner_id, name: c.name, choice: choice.value, label: choice.label })
                        }
                      >
                        {choice.label}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="muted">{t('ballot.unavailable')}</p>
                )}
              </div>
            ))}
          </div>
          {pending && (
            <div className="vote-confirmation" role="group" aria-label={t('ballot.confirmButton')}>
              <p>{t('ballot.confirm', { choice: pending.label, name: pending.name })}</p>
              <p className="muted">{t('ballot.final')}</p>
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await api(path(`/rounds/${r.id}/ballots`), {
                      owner_id: pending.ownerId,
                      choice: pending.choice,
                      proposal_hash: r.hash,
                    });
                    setPending(null);
                  }, t('ballot.done'))
                }
              >
                {t('ballot.confirmButton')}
              </button>
              <button disabled={busy} onClick={() => setPending(null)}>
                {t('ballot.cancel')}
              </button>
            </div>
          )}
          {president && (
            <button
              className="outline"
              disabled={busy}
              onClick={() => {
                if (window.confirm(t('ballot.closeConfirm')))
                  run(() => api(path(`/rounds/${r.id}/close`), {}), t('ballot.closedMsg'));
              }}
            >
              {t('ballot.closeEarly')}
            </button>
          )}
        </>
      ) : (
        r.result && <ResultView round={r} choiceLabel={choiceLabel} />
      )}
    </section>
  );
}

function ResultView({ round: r, choiceLabel }: { round: RoundState; choiceLabel: (value: string) => string }) {
  const { t } = useI18n();
  const result = r.result!;
  const approved = result.outcome === 'APPROVED' || result.outcome === 'ELECTED';
  return (
    <>
      <div className={'result' + (approved ? ' approved' : '')}>
        {r.kind === 'ELECTION' ? (
          <>
            <span>{t(`result.${result.outcome}` as MessageKey, { name: (result as ElectionResult).winner?.label ?? '' })}</span>
            <table className="election-table">
              <thead>
                <tr>
                  <th>{t('result.candidate')}</th>
                  <th>{t('result.votes')}</th>
                </tr>
              </thead>
              <tbody>
                {(result as ElectionResult).options.map((o) => (
                  <tr key={o.id}>
                    <td>{o.label}</td>
                    <td>{o.votes}</td>
                  </tr>
                ))}
                <tr>
                  <td>{t('choice.BLANK')}</td>
                  <td>{(result as ElectionResult).blank}</td>
                </tr>
              </tbody>
            </table>
          </>
        ) : (
          <>
            <span>{t(`result.${result.outcome}` as MessageKey)}</span>
            <strong>
              {(result as SimpleResult).yes} {t('choice.YES')} <small>·</small> {(result as SimpleResult).no} {t('choice.NO')}{' '}
              <small>·</small> {(result as SimpleResult).abstain} {t('choice.ABSTAIN')}
            </strong>
          </>
        )}
        <p>{t('result.notVoted', { n: result.not_voted })}</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{r.voting_mode === 'SECRET' ? t('result.votedSecret') : t('result.owner')}</th>
              <th>{t('result.executor')}</th>
              {r.voting_mode === 'NOMINAL' && <th>{t('result.vote')}</th>}
            </tr>
          </thead>
          <tbody>
            {(r.voting_mode === 'SECRET' ? r.participants : r.nominal_votes).map((v) => (
              <tr key={v.protocol}>
                <td>{v.owner_name}</td>
                <td>{v.executor_name}</td>
                {r.voting_mode === 'NOMINAL' && <td>{v.choice ? choiceLabel(v.choice) : ''}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
